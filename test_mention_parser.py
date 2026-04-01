from mention_parser import parse

def test_parse():
    # 케이스 1: 지원되는 멘션이 있는 경우
    res1 = parse("@claude 리팩토링해줘")
    print(f"res1: {res1}")
    assert res1 == {"target": "claude", "text": "리팩토링해줘"}

    # 케이스 2: 멘션이 없는 경우
    res2 = parse("계속 진행해줘")
    print(f"res2: {res2}")
    assert res2 == {"target": None, "text": "계속 진행해줘"}

    # 케이스 3: 지원되지 않는 멘션이 있는 경우
    res3 = parse("@unknown 작업")
    print(f"res3: {res3}")
    # 미지원 멘션은 무시한다고 했으니 target=None 반환
    assert res3["target"] == None

    # 케이스 4: 대소문자 무관한지 확인 (추가)
    res4 = parse("@GEMINI 안녕")
    print(f"res4: {res4}")
    assert res4 == {"target": "gemini", "text": "안녕"}

    print("모든 테스트 통과!")

if __name__ == "__main__":
    test_parse()
