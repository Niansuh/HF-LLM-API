import base64
from hashlib import sha3_512
import json
import random

from datetime import datetime, timedelta, timezone

from constants.headers import OPENAI_GET_HEADERS


class ProofWorker:
    def __init__(self, user_name, difficulty=None, required=False, seed=None):
        self.user_name = user_name
        self.difficulty = difficulty
        self.required = required
        self.seed = seed
        self.proof_token_prefix = "gAAAAABwQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def get_parse_time(self):
        now = datetime.now()
        tz = timezone(timedelta(hours=8))
        now = now.astimezone(tz)
        time_format = "%a %b %d %Y %H:%M:%S"
        return now.strftime(time_format) + " GMT+0800 (中国标准时间)"

    def get_config(self):
        cores = [8, 12, 16, 24]
        core = random.choice(cores)
        screens = [3000, 4000, 6000]
        screen = random.choice(screens)
        return [
            str(core) + str(screen),
            self.get_parse_time(),
            4294705152,
            0,
            OPENAI_GET_HEADERS["User-Agent"],
        ]

    def calc_proof_token(self, seed: str, difficulty: str):
        try:
            config = self.get_config()
            diff_len = len(difficulty) // 2
            for i in range(100000):
                config[3] = i
                json_str = json.dumps(config)
                base = base64.b64encode(json_str.encode()).decode()
                hasher = sha3_512()
                hasher.update((seed + base).encode())
                hash_val = hasher.digest().hex()
                if hash_val[:diff_len] <= difficulty:
                    return "gAAAAAB" + base
            self.proof_token = (
                self.proof_token_prefix + base64.b64encode(seed.encode()).decode()
            )
            return self.proof_token
        except Exception as e:
            return str(e)


if __name__ == "__main__":
    user_name = "Niansuh"
    seed, difficulty = "0.42665582693491433", "05cdf2"
    worker = ProofWorker(user_name)
    proof_token = worker.calc_proof_token(seed, difficulty)
    decoded_proof_token = base64.b64decode(proof_token.encode()).decode()
    print(f"proof_token: {proof_token}")
    print(f"decoded_proof_token: {decoded_proof_token}")
    # python -m networks.proof_worker
