import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback
from fab_env import FabEnv  # 우리가 만든 환경

def train_agent():
    print("🚀 강화학습(PPO) 에이전트 학습 시작")
    print("-" * 60)

    # 1. 환경 생성 및 래핑
    # DummyVecEnv는 여러 환경을 동시에 돌릴 때 쓰지만, 1개일 때도 호환성을 위해 씀
    env = DummyVecEnv([lambda: FabEnv()])

    # 2. PPO 모델 정의
    # MlpPolicy: 입력이 이미지(CNN)가 아니라 숫자 벡터일 때 사용
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=1, 
        learning_rate=0.0003,
        n_steps=2048, 
        batch_size=64,
        gamma=0.99
    )

    # 3. 모델 저장용 콜백 (1만 스텝마다 저장)
    checkpoint_callback = CheckpointCallback(
        save_freq=10000, 
        save_path='./logs/', 
        name_prefix='ppo_smt'
    )

    # 4. 학습 시작 (예: 10만 스텝)
    print("🧠 학습 진행 중...")
    model.learn(total_timesteps=3000000, callback=checkpoint_callback)

    # 5. 모델 저장
    model.save("ppo_smt_final")
    print("💾 최종 모델 저장 완료: ppo_smt_final.zip")

if __name__ == "__main__":
    train_agent()