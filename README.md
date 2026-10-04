# CS KOREA 입찰공고 센터

나라장터의 교육·행사·전시·연수 관련 입찰공고를 자동으로 수집하고, 울산시·5개 구군·울산교육청·전국 공고로 나눠 보여주는 사내용 웹 화면입니다.

직원은 인터넷 주소만 열면 됩니다. **ChatGPT 로그인과 API 키 입력은 필요 없습니다.** API 키는 관리자가 GitHub에 처음 한 번만 등록합니다.

## 현재 포함된 기능

- 용역 공고 기본 수집
- 물품·공사 수집 선택 가능
- 울산광역시 본청, 5개 구·군, 울산광역시교육청 분류
- 학교·유치원 공고 선택 기능(기본 꺼짐)
- 전국 공고는 설정 키워드와 참가 가능 지역을 함께 확인
- 공고 마감일과 D-day 표시
- 마감된 공고 자동 숨김
- 평일 오전 9시 10분·오후 4시 10분 자동 갱신
- 서버·데이터베이스·카카오톡·로그인·유료 서비스 없음

## 폴더 구성

```text
collector/                 나라장터 수집·정리·필터 코드
mock/                      화면 확인용 모의 API 응답
public/                    직원들이 보는 정적 웹 화면
public/data/bids.json      화면에 표시할 공고 데이터
scripts/validate_data.py   새 데이터 안전성 검사
tests/                     자동검사
.github/workflows/         자동 수집·GitHub Pages 배포 설정
config.json                기관·키워드·수집 종류 설정
```

## 1. GitHub 저장소 만들기

1. [GitHub](https://github.com/)에 로그인합니다.
2. 오른쪽 위 `+`를 누르고 `New repository`를 선택합니다.
3. 저장소 이름을 `cskorea-bid-center`로 입력합니다.
4. 무료 GitHub Pages 사용을 위해 `Public`을 선택합니다.
5. `Create repository`를 누릅니다.
6. 이 압축파일을 풀고, 안의 `cskorea-bid-center` 폴더 내용을 저장소에 올립니다.

> 공개 저장소에는 소스코드와 공고 JSON이 보이지만 API 키는 들어가지 않습니다.

## 2. 나라장터 API 키 한 번만 등록하기

API 키를 채팅이나 소스파일에 붙여 넣지 마십시오.

1. GitHub 저장소에서 `Settings`를 엽니다.
2. 왼쪽에서 `Secrets and variables` → `Actions`를 누릅니다.
3. `New repository secret`을 누릅니다.
4. 이름에는 정확히 `G2B_SERVICE_KEY`를 입력합니다.
5. `Secret` 칸에 공공데이터포털에서 발급받은 나라장터 일반 인증키를 붙여 넣습니다.
6. `Add secret`을 누릅니다.

이후에는 직원이나 대표가 앱을 열 때 API 키를 다시 입력할 필요가 없습니다.

## 3. GitHub Pages 켜기

1. 저장소의 `Settings` → `Pages`로 이동합니다.
2. `Build and deployment`의 Source를 `GitHub Actions`로 선택합니다.
3. 저장소 위쪽 `Actions` 메뉴를 엽니다.
4. `나라장터 수집 및 배포` 작업을 선택합니다.
5. `Run workflow`를 눌러 첫 수집을 실행합니다.
6. 작업이 초록색 체크로 끝나면 `deploy` 단계에 표시된 인터넷 주소를 엽니다.

이후 평일 오전 9시 10분과 오후 4시 10분에 자동으로 실행됩니다. GitHub 일정 작업은 서버 상황에 따라 몇 분 늦어질 수 있습니다.

## 4. 직원 컴퓨터에서 사용하기

세 컴퓨터 모두 같은 GitHub Pages 주소를 사용합니다.

1. 크롬이나 엣지에서 배포된 주소를 엽니다.
2. 브라우저 메뉴에서 `바로가기 만들기` 또는 `앱으로 설치`를 선택합니다.
3. `바탕화면에 추가`를 선택합니다.

이제 바탕화면 아이콘을 누르면 최신 공고 화면이 열립니다. 별도의 ChatGPT 계정은 필요하지 않습니다.

## 5. 기관과 키워드 바꾸기

루트의 `config.json`만 수정하면 됩니다.

### 수집 종류

```json
"categories": {
  "services": true,
  "goods": false,
  "construction": false
}
```

- `true`: 수집함
- `false`: 수집하지 않음

### 포함 키워드

`filters.keywords` 배열에 단어를 추가하거나 삭제합니다.

기본값은 교육, 행사, 박람회, 전시, 국제교류, 홍보, 연수, 포럼, 관광, 운영 용역, 행사대행입니다.

### 제외 키워드

원하지 않는 공고는 `filters.exclude_keywords`에 단어를 넣습니다.

```json
"exclude_keywords": ["시설공사", "급식"]
```

포함 키워드와 제외 키워드가 동시에 들어간 공고는 제외됩니다.

### 학교 공고 켜기

`ulsan_schools` 항목의 `enabled`를 `false`에서 `true`로 바꿉니다.

## 6. 컴퓨터에서 모의 데이터로 확인하기

Python 3가 설치된 컴퓨터에서 프로젝트 폴더를 열고 실행합니다.

```bash
python -m collector.collect --mock-dir mock
python -m http.server 8000 -d public
```

그 다음 브라우저에서 `http://localhost:8000`을 엽니다.

## 7. 자동검사

```bash
python -m unittest discover -s tests -v
```

모든 항목 끝에 `ok`가 표시되면 정상입니다.

## 실제 API 연결 전 최종 확인사항

현재 화면과 자동화는 모의 응답으로 검증되었습니다. 실제 API 키로 처음 실행할 때 다음 항목을 반드시 확인해야 합니다.

1. `config.json`의 API 기본주소와 활용신청한 서비스 주소가 같은지
2. 용역 조회 오퍼레이션이 정상 응답하는지
3. 공고번호, 공고명, 기관명, 공고일시, 마감일시, 추정가격, 상세주소 필드가 실제 JSON에 존재하는지
4. 참가 가능 지역 값이 `전국`, `울산광역시` 등으로 정상 제공되는지
5. 전국 공고가 너무 적으면 별도의 참가 가능 지역 조회 오퍼레이션을 연결해야 하는지

응답 형식이 다르면 추측해서 고치지 말고, 실제 JSON 한 건에서 필드명을 확인한 다음 `collector/collect.py`의 `normalize_item()` 매핑을 수정합니다.

## 문제 해결

### `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`

- API 활용신청이 완료됐는지 확인합니다.
- GitHub Secret 이름이 정확히 `G2B_SERVICE_KEY`인지 확인합니다.
- 일반 인증키와 인코딩 인증키 중 공공데이터포털 안내에 맞는 키를 사용했는지 확인합니다.

### 화면에 `모의 데이터`라고 나오는 경우

아직 실제 API 수집이 성공하지 않은 상태입니다. GitHub의 `Actions`에서 실패한 단계의 기록을 확인합니다.

### 전국 공고가 보이지 않는 경우

전국 분류는 키워드뿐 아니라 참가 가능 지역도 확인합니다. 지역정보가 없는 공고는 잘못 포함되는 것을 막기 위해 기본적으로 제외합니다.

### 예정된 시간에 바로 실행되지 않는 경우

GitHub 예약 작업은 혼잡할 때 지연될 수 있습니다. `Actions` → `나라장터 수집 및 배포` → `Run workflow`를 누르면 즉시 실행할 수 있습니다.

## 보안 원칙

- API 키를 `config.json`, 자바스크립트, JSON 또는 README에 입력하지 않습니다.
- API 키는 GitHub Actions Secret에만 저장합니다.
- 직원에게는 배포된 인터넷 주소만 전달합니다.
- 공고 자료는 공개정보이지만 내부 검토 의견이나 개인정보는 이 정적 사이트에 저장하지 않습니다.

## 운영 구조

```text
나라장터 OpenAPI → GitHub Actions 자동수집 → 정적 bids.json 생성
                                    ↓
                             GitHub Pages 배포
                                    ↓
                         직원 3명 브라우저에서 확인
```

최종 운영 전에는 실제 API 키로 한 번 수동 실행하여 데이터와 나라장터 원문을 대조하십시오.
