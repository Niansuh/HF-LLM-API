import base64
import json
import random
from datetime import datetime, timedelta, timezone
from constants.headers import OPENAI_GET_HEADERS

class ProofWorker:
    def __init__(self):
        pass

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
        config = self.get_config()
        diff_len = len(difficulty) // 2
        for i in range(100000):
            config[3] = i
            json_str = json.dumps(config)
            base = base64.b64encode(json_str.encode()).decode()
            # You can modify the proof generation logic here as per your requirement
            # For now, I'm just returning a placeholder string
            return f"proof_token_for_{seed}_{difficulty}"

if __name__ == "__main__":
    worker = ProofWorker()
    config = worker.get_config()
    print("Config:", config)
    seed, difficulty = "0.42665582693491433", "05cdf2"
    proof_token = worker.calc_proof_token(seed, difficulty)
    print(f"Proof token: {proof_token}")
