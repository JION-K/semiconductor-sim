import gymnasium as gym
from fab_env import FabEnv  # 방금 만든 fab_env.py에서 클래스 가져오기
import numpy as np

def test_environment():
    print("🧪 환경 검증 테스트 시작 (Random Agent Mode)")
    print("-" * 60)

    # 1. 환경 생성
    try:
        env = FabEnv()
        print("✅ FabEnv 환경 생성 성공")
    except Exception as e:
        print(f"❌ 환경 생성 실패: {e}")
        return

    # 2. Reset 테스트
    try:
        obs, info = env.reset()
        print(f"✅ Reset 성공! 초기 관측값(State) 크기: {obs.shape}")
        print(f"   - 관측값 예시: {obs[:10]} ...") # 앞부분만 살짝 보기
    except Exception as e:
        print(f"❌ Reset 실패: {e}")
        return

    # 3. Step 루프 테스트 (랜덤 행동)
    print("-" * 60)
    print("🏃 시뮬레이션 주행 시작 (100 Step 진행)...")
    
    total_reward = 0
    done = False
    step_count = 0

    try:
        while not done and step_count < 100:
            # (1) 랜덤 행동 선택 (0 ~ 9 사이의 숫자)
            action = env.action_space.sample()
            
            # (2) 환경에 행동 전달
            obs, reward, terminated, truncated, info = env.step(action)
            
            total_reward += reward
            step_count += 1
            done = terminated or truncated

            # 로그 출력 (너무 많으면 정신없으니 10번에 1번만)
            if step_count % 10 == 0:
                print(f"   [Step {step_count}] Action: {action} -> Reward: {reward:.4f}")

        print("-" * 60)
        print(f"✅ 테스트 완료! (총 {step_count} 스텝)")
        print(f"💰 획득한 총 보상: {total_reward:.4f}")
        
    except Exception as e:
        print(f"❌ 시뮬레이션 도중 에러 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        env.close()

if __name__ == "__main__":
    test_environment()