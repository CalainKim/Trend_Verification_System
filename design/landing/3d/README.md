# 첫 화면 3D 영상

랜딩 첫 화면의 장면 네 개를 Blender 로 만드는 스크립트다. 장면을 마우스로
만들지 않고 Python 으로 생성하므로, 고칠 때는 스크립트를 고치고 다시 렌더한다.

```
s1_collect.py   01 수집     채널 로고 타일에서 구슬이 흘러나와 가운데 코어로 모인다
s2_detect.py    02 판별     들쭉날쭉한 리본 사이로 주황 관 하나가 꾸준히 솟는다
s3_cutoff.py    03 누수 차단 시점 왼쪽 막대만 솟고 유리벽 너머는 가려진다
s4_verdict.py   04 판정     구슬이 확정, 보류, 기각 세 고리로 갈라진다
common.py       렌더 설정, 재질, 조명, 카메라 도구
tex/            타일에 붙이는 로고와 글자 질감
```

## 렌더

Blender 5.2 와 ffmpeg 가 필요하다 (`brew install --cask blender`, `brew install ffmpeg`).

```
blender -b -P s1_collect.py -- preview still=80   # 미리보기 한 장 (EEVEE, 몇 초)
blender -b -P s1_collect.py                        # 가로 1600x900 130장 (Cycles)
blender -b -P s1_collect.py -- portrait            # 폰용 세로 720x1280
./render_all.sh                                    # 가로 네 장면을 렌더하고 mp4 로
./render_mobile.sh                                 # 가로가 끝나면 세로 네 장면
```

M4 맥에서 장면 하나가 10분 안팎이다. 결과는 `out/` 과 `video/` 에 생기고
저장소에는 넣지 않는다. 완성된 영상은 `../assets/hero/` (가로) 와
`../assets/hero/m/` (세로) 에 복사한다.

색은 V9 디자인 시스템(주황, 단계 파스텔)을 쓴다. 랜딩 아래 섹션은 2026-11-08 에
무신사 흑백으로 바꿨지만 영상은 그대로 두기로 했다.
