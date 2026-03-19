import gymnasium as gym
from stable_baselines3 import PPO
from fab_env import FabEnv
import numpy as np

def test_trained_model():
    print("🤖 학습된 모델(PPO) 성능 검증 시작")
    print("-" * 60)

    # 1. 환경 생성 (학습 때와 동일한 설정)
    env = FabEnv()
    
    # 2. 저장된 모델 불러오기
    # (같은 폴더에 ppo_smt_final.zip 파일이 있어야 함)
    try:
        model = PPO.load("ppo_smt_final")
        print("✅ 모델 로딩 성공!")
    except FileNotFoundError:
        print("❌ 모델 파일을 찾을 수 없습니다. 파일명을 확인해주세요.")
        return

    # 3. 시뮬레이션 돌리기 ()
    obs, info = env.reset()
    done = False
    total_reward = 0
    steps = 0

    print("🏃 시뮬레이션 주행 중... (약 90일 가상 시간)")
    
    while not done:
        # 모델에게 관측값(obs)을 주고 행동(action)을 예측하게 함
        # deterministic=True: 학습된 대로만 행동 (랜덤성 배제)
        action, _states = model.predict(obs, deterministic=True)
        
        obs, reward, terminated, truncated, info = env.step(action)
        
        total_reward += reward
        steps += 1
        done = terminated or truncated

        # 진행 상황 표시 (선택 사항)
        if steps % 1000 == 0:
            print(f"   Step {steps} 진행 중... (현재 시간: {env.sim_env.now:.1f}분)")

    print("-" * 60)
    print("📊 최종 검증 결과")
    print(f"   - 총 스텝 수: {steps}")
    print(f"   - 총 획득 보상: {total_reward:.2f}")
    
    # 환경 내부에 구현된 print_kpi 함수 호출 (KPI 리포트)
    # fab_env.py 안에 kpi 데이터를 출력하는 로직이 있다면 활용
    if hasattr(env, 'kpi'):
        lots = env.kpi['lots']
        if len(lots) > 0:
            avg_tat = np.mean([l.get_tat() for l in lots])
            print(f"   - 🏭 생산된 Lot 수: {len(lots)}개")
            print(f"   - ⏱️ 평균 TAT: {avg_tat:.2f}분")
            print(f"   - ⚠️ Q-Time 위반 수: {sum([l.q_time_violations for l in lots])}회")
        else:
            print("   ⚠️ 완료된 Lot이 하나도 없습니다.")

if __name__ == "__main__":
    test_trained_model()