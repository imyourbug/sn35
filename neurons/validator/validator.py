import time
import datetime
import bittensor as bt
import random
import torch
from logicnet.base.validator import BaseValidatorNeuron
from neurons.validator.validator_proxy import ValidatorProxy
import logicnet as ln
from logicnet.validator import MinerManager, LogicChallenger, LogicRewarder, MinerInfo
from logicnet.utils.wandb_manager import WandbManager
import traceback
import threading
from neurons.validator.core.serving_queue import QueryQueue
import requests


def init_category(config=None):
    category = {
        "Logic": {
            "synapse_type": ln.protocol.LogicSynapse,
            "incentive_weight": 1.0,
            "challenger": LogicChallenger(
                config.llm_client.base_url,
                config.llm_client.key,
                config.llm_client.model,
            ),
            "rewarder": LogicRewarder(
                config.llm_client.base_url,
                config.llm_client.key,
                config.llm_client.model,
            ),
            "timeout": 64,
        }
    }
    return category


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        """
        MAIN VALIDATOR that run the synthetic epoch and opening a proxy for receiving queries from the world.
        """
        super(Validator, self).__init__(config=config)
        bt.logging.info("\033[1;32m🧠 load_state()\033[0m")
        self.categories = init_category(self.config)
        self.miner_manager = MinerManager(self)
        self.load_state()
        self.update_scores_on_chain()
        self.sync()
        self.miner_manager.update_miners_identity()
        self.wandb_manager = WandbManager(neuron = self)
        self.query_queue = QueryQueue(
            list(self.categories.keys()),
            time_per_loop=self.config.loop_base_time,
        )
        if self.config.proxy.port:
            try:
                self.validator_proxy = ValidatorProxy(self)
                bt.logging.info(
                    "\033[1;32m🟢 Validator proxy started successfully\033[0m"
                )
            except Exception:
                bt.logging.warning(
                    "\033[1;33m⚠️ Warning, proxy did not start correctly, so no one can query through your validator. "
                    "This means you won't participate in queries from apps powered by this subnet. Error message: "
                    + traceback.format_exc()
                    + "\033[0m"
                )

    def forward(self):
        """
        Query miners by batched from the serving queue then process challenge-generating -> querying -> rewarding in background by threads
        DEFAULT: 16 miners per batch, 600 seconds per loop.
        """
        self.store_miner_infomation()
        bt.logging.info("\033[1;34m🔄 Updating available models & uids\033[0m")
        async_batch_size = self.config.async_batch_size
        loop_base_time = self.config.loop_base_time  # default is 600 seconds
        threads = []
        loop_start = time.time()
        self.miner_manager.update_miners_identity()
        self.query_queue.update_queue(self.miner_manager.all_uids_info)
        self.miner_uids = []
        self.miner_scores = []
        self.miner_reward_logs = []

        # Set up wandb log
        if not self.config.wandb.off:
            today = datetime.date.today()
            if (self.wandb_manager.wandb_start_date != today and 
                hasattr(self.wandb_manager, 'wandb') and 
                self.wandb_manager.wandb is not None):
                self.wandb_manager.wandb.finish()
                self.wandb_manager.init_wandb()

        # Query and reward
        for (
            category,
            uids,
            should_rewards,
            sleep_per_batch,
        ) in self.query_queue.get_batch_query(async_batch_size):
            bt.logging.info(
                f"\033[1;34m🔍 Querying {len(uids)} uids for model {category}, sleep_per_batch: {sleep_per_batch}\033[0m"
            )

            thread = threading.Thread(
                target=self.async_query_and_reward,
                args=(category, uids, should_rewards),
            )
            threads.append(thread)
            thread.start()

            bt.logging.info(
                f"\033[1;34m😴 Sleeping for {sleep_per_batch} seconds between batches\033[0m"
            )
            time.sleep(sleep_per_batch)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Assign incentive rewards
        self.assign_incentive_rewards(self.miner_uids, self.miner_scores, self.miner_reward_logs)

        # Update scores on chain
        self.update_scores_on_chain()
        self.save_state()
        bt.logging.info(
            "\033[1;32m✅ Loop completed, uids info:\n"
            + str(self.miner_manager.all_uids_info).replace("},", "},\n")
            + "\033[0m"
        )
        self.store_miner_infomation()

        actual_time_taken = time.time() - loop_start

        if actual_time_taken < loop_base_time:
            bt.logging.info(
                f"\033[1;34m😴 Sleeping for {loop_base_time - actual_time_taken} seconds\033[0m"
            )
            time.sleep(loop_base_time - actual_time_taken)

    def async_query_and_reward(
        self,
        category: str,
        uids: list[int],
        should_rewards: list[int],
    ):
        dendrite = bt.dendrite(self.wallet)
        uids_should_rewards = list(zip(uids, should_rewards))
        synapses, batched_uids_should_rewards = self.prepare_challenge(
            uids_should_rewards, category
        )
        
        for synapse, uids_should_rewards in zip(synapses, batched_uids_should_rewards):
            uids, should_rewards = zip(*uids_should_rewards)
            bt.logging.info(
                f"\033[1;34m🔍 Querying {uids}, Should reward: {should_rewards}\033[0m"
            )
            if not synapse:
                continue
            base_synapse = synapse.copy()
            synapse = synapse.miner_synapse()
            axons = [self.metagraph.axons[int(uid)] for uid in uids]
            bt.logging.debug(f"\033[1;34m🧠 Axon: {axons}\033[0m")
            responses = dendrite.query(
                axons=axons,
                synapse=synapse,
                deserialize=False,
                timeout=self.categories[category]["timeout"],
            )
            bt.logging.debug(
                f"\033[1;34m🧠 Miner response: {responses[0].logic_answer}\033[0m"
            )
            reward_responses = [
                response
                for response, should_reward in zip(responses, should_rewards)
                if should_reward
            ]
            reward_uids = [
                uid for uid, should_reward in zip(uids, should_rewards) if should_reward
            ]

            bt.logging.info(
                f"\033[1;34m🔍 Received {len(responses)} responses, {len(reward_responses)} to be rewarded\033[0m"
            )

            if reward_uids:
                uids, rewards, reward_logs = self.categories[category]["rewarder"](
                    reward_uids, reward_responses, base_synapse
                )

                for i, uid in enumerate(reward_uids):
                    if rewards[i] > 0:
                        rewards[i] = rewards[i] * (
                            0.9
                            + 0.1 * self.miner_manager.all_uids_info[uid].reward_scale
                        )

                bt.logging.info(f"\033[1;32m🏆 Scored responses: {rewards}\033[0m")

                if rewards and reward_logs and uids: 
                    self.miner_reward_logs.append(reward_logs)
                    self.miner_uids.append(uids) 
                    self.miner_scores.append(rewards)

    def assign_incentive_rewards(self, uids, rewards, reward_logs):
        """
        Calculate incentive rewards based on the rank.
        Get the incentive rewards for the valid responses using the cubic function and valid_rewards rank.
        """
        # Flatten the nested lists
        flat_uids = [uid for uid_list in uids for uid in uid_list]
        flat_rewards = [reward for reward_list in rewards for reward in reward_list]
        flat_reward_logs = [log for log_list in reward_logs for log in log_list]

        # Enumerate rewards with their original index
        original_rewards = list(enumerate(flat_rewards))
        
        # Sort rewards in descending order based on the score
        sorted_rewards = sorted(original_rewards, key=lambda x: x[1], reverse=True)
        
        # Calculate ranks, handling ties
        ranks = []
        previous_score = None
        rank = 0
        for i, (reward_id, score) in enumerate(sorted_rewards):
            rank = i + 1 if score != previous_score else rank  # Update rank only if the score changes
            ranks.append((reward_id, rank, score))
            previous_score = score
        
        # Restore the original order of rewards
        ranks.sort(key=lambda x: x[0])

        # Calculate incentive rewards based on the rank, applying the cubic function for positive scores
        def incentive_formula(rank):
            reward_value = -1.038e-7 * rank**3 + 6.214e-5 * rank**2 - 0.0129 * rank - 0.0118
            # Scale up the reward value between 0 and 1
            scaled_reward_value = reward_value + 1
            return scaled_reward_value
        
        incentive_rewards = [
            (incentive_formula(rank) if score > 0 else 0) for _, rank, score in ranks
        ]
        
        # Update scores on chain
        self.miner_manager.update_scores(flat_uids, incentive_rewards, flat_reward_logs)
        
        # Reset the miner reward logs, uids, and scores for next loop
        self.miner_scores = []
        self.miner_reward_logs = []
        self.miner_uids = []

    def prepare_challenge(self, uids_should_rewards, category):
        """
        Prepare the challenge for the miners. Continue batching to smaller.
        """
        synapse_type = self.categories[category]["synapse_type"]
        challenger = self.categories[category]["challenger"]
        timeout = self.categories[category]["timeout"]
        model_miner_count = len(
            [
                uid
                for uid, info in self.miner_manager.all_uids_info.items()
                if info.category == category
            ]
        )
        # The batch size is 8 or the number of miners
        batch_size = min(8, model_miner_count)
        random.shuffle(uids_should_rewards)
        batched_uids_should_rewards = [
            uids_should_rewards[i * batch_size : (i + 1) * batch_size]
            for i in range((len(uids_should_rewards) + batch_size - 1) // batch_size)
        ]
        num_batch = len(batched_uids_should_rewards)

        synapses = [
            synapse_type(category=category, timeout=timeout) for _ in range(num_batch)
        ]
        for synapse in synapses:
            synapse = challenger(synapse)

        return synapses, batched_uids_should_rewards

    def update_scores_on_chain(self):
        """Performs exponential moving average on the scores based on the rewards received from the miners."""

        weights = torch.zeros(len(self.miner_manager.all_uids))
        for category in self.categories.keys():
            model_specific_weights = self.miner_manager.get_model_specific_weights(
                category
            )
            model_specific_weights = (
                model_specific_weights * self.categories[category]["incentive_weight"]
            )
            bt.logging.info(
                f"\033[1;34m⚖️ model_specific_weights for {category}\n{model_specific_weights}\033[0m"
            )
            weights = weights + model_specific_weights

        # Check if rewards contains NaN values.
        if torch.isnan(weights).any():
            bt.logging.warning(
                f"\033[1;33m⚠️ NaN values detected in weights: {weights}\033[0m"
            )
            # Replace any NaN values in rewards with 0.
            weights = torch.nan_to_num(weights, 0)
        self.scores: torch.FloatTensor = weights
        bt.logging.success(f"\033[1;32m✅ Updated scores: {self.scores}\033[0m")

    def save_state(self):
        """Saves the state of the validator to a file."""

        torch.save(
            {
                "step": self.step,
                "all_uids_info": self.miner_manager.all_uids_info,
            },
            self.config.neuron.full_path + "/state.pt",
        )

    def load_state(self):
        """Loads the state of the validator from a file."""

        # Load the state of the validator from file.
        try:
            path = self.config.neuron.full_path + "/state.pt"
            bt.logging.info(
                "\033[1;32m🧠 Loading validator state from: " + path + "\033[0m"
            )
            state = torch.load(path)
            self.step = state["step"]
            all_uids_info = state["all_uids_info"]
            for k, v in all_uids_info.items():
                v = v.to_dict()
                self.miner_manager.all_uids_info[k] = MinerInfo(**v)
            bt.logging.info("\033[1;32m✅ Successfully loaded state\033[0m")
        except Exception as e:
            self.step = 0
            bt.logging.info(
                "\033[1;33m⚠️ Could not find previously saved state.\033[0m", e
            )

    def store_miner_infomation(self):
        miner_informations = self.miner_manager.to_dict()

        def _post_miner_informations(miner_informations):
            requests.post(
                url=self.config.storage.storage_url,
                json={
                    "miner_information": miner_informations,
                    "validator_uid": int(self.uid),
                },
            )

        thread = threading.Thread(
            target=_post_miner_informations,
            args=(miner_informations,),
        )
        thread.start()


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info("\033[1;32m🟢 Validator running...\033[0m", time.time())
            time.sleep(360)
