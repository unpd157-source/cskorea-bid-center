# CS KOREA 입찰정보 포털

나라장터 용역 공고를 키워드로 수집하여 GitHub Pages에 게시합니다.
공개 사이트이며 직원 전용 로그인, 공고 선정 공유, AI 과업 분석은 아직 없습니다.

## 운영
- API 키: GitHub Actions Secret `G2B_SERVICE_KEY`에 저장. 브라우저에 키를 넣지 않습니다.
- 자동 수집: 평일 09:10 / 16:10 Asia/Seoul. GitHub 실행은 지연될 수 있습니다.
- `자료 새로고침`: 저장된 공고와 수집 상태를 다시 불러옵니다. 열린 화면은 5분마다 새 자료를 확인합니다.
- `관리자 재수집`: GitHub Actions 페이지에서 관리자가 `Run workflow`를 눌러 실제 API 수집을 시작합니다. GitHub 로그인·저장소 실행 권한이 필요합니다.
- 마감 시간은 한국 시간으로 판정하고 1분마다 화면에서 재계산합니다.

## 수집 범위와 제한
- 용역만 기본 활성화. 교육·행사·박람회·전시·국제교류·홍보·연수·포럼·관광·운영 용역·행사대행 제목 키워드 사용.
- 울산 분류는 기관명 기준입니다. 울산에 있는 모든 기관의 소재지를 검증한 목록이 아닙니다. 이름에 울산이 없는 기관은 전국 탭에서 검색하세요.
- 전국 탭은 지역정보가 없거나 다른 지역으로 표시된 공고도 수록합니다. 전국 참가 가능 또는 CS KOREA 입찰 가능 판정을 의미하지 않습니다. 자격·지역 제한은 원문 확인이 필요합니다.
- 교육청 분류에 강남·강북 교육지원청을 포함합니다.
- 울산시·교육청 자체 사이트는 직접 수집하지 않습니다.

## 장애와 보관
- 요청 제한시간 60초, 최대 4회 시도(2·4·8초 간격 재시도).
- API 응답 구조, 공고번호·제목·날짜·중복·개수 검증 후 원자적으로 저장합니다.
- 통신 오류·잘못된 응답·API 전체 0건이면 기존 자료 유지. `status.json`에 실패 표시를 게시합니다.
- 매번 최근 30일 공고를 수집하고 이전 실제 데이터와 ID 기준 병합합니다. 이미 확보한 이전 공고는 누적 보관합니다. 수정·취소가 조회 범위 밖에서 일어난 경우 원문 대조가 필요합니다.
- 처음부터 수집되지 않았던 30일 이전 자료는 자동 복구되지 않습니다.
- 마지막 수집 후 18시간이 지나면 최신성 경고를 표시합니다.
- 코드 push는 검사 후 화면만 배포합니다. 수집은 schedule 또는 workflow_dispatch에서 실행합니다.

## 파일 및 검사
- `collector/collect.py`: 수집·재시도·분류·병합·상태 저장
- `scripts/validate_data.py`: 운영 데이터 검증
- `config.json`: 키워드·기관·수집 설정
- `public/`: 배포 원본
- `.github/workflows/collect-and-deploy.yml`: 검사·수집·상태 게시·배포
- `tests/`: 회귀 검사

```bash
python3 -m unittest discover -s tests -v
node --check public/app.js
```

모의 데이터는 반드시 운영 파일과 분리합니다.
```bash
python3 -m collector.collect --mock-dir mock --output /tmp/cskorea-demo.json
```
기본 운영 출력 경로로 모의 데이터를 쓰려 하면 거부합니다.
`public/data/bids.json`은 원격 최신 실제 파일을 사용하세요. 오래된 로컬 모의 데이터를 업로드하지 마세요.
`dist`는 `python3 scripts/build_static.py`로 생성하는 결과물이며 GitHub Pages는 `public`을 직접 배포합니다.

## 배포
운영 주소: https://unpd157-source.github.io/cskorea-bid-center/
Vercel 배포는 연결되어 있지 않습니다.
