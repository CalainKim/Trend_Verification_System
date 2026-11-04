# 번들에 같이 넣는 바깥 라이브러리

화면을 파일 하나로 묶을 때 여기 있는 셋을 그대로 집어넣는다.
`scripts/bundle_design.py` 의 `inline_vendor()` 가 한다.

    react.production.min.js        10,751 바이트
    react-dom.production.min.js   131,835 바이트
    babel.min.js                3,137,752 바이트

## 왜 저장소에 넣어 두나

`support.js` 는 맨 끝에서 `loadReactUmd().then(init)` 을 부른다. React 를
받아온 뒤에야 화면을 그린다는 뜻이다. 번들에 React 가 없으면 인터넷이
없는 자리에서 **빈 화면**이 된다. 교수님 방이나 무신사 회의실에서 와이파이가
안 잡히면 그대로 아무것도 안 뜬다. v8 로 만든 파일이 그 상태였다.

Babel 은 v9 부터 필요해졌다. v9 는 React 컴포넌트 일곱을
`x-import ... from="./PillNavV.jsx"` 로 불러오고, 런타임이 그 파일을 읽어
Babel 로 바꿔서 실행한다. Babel 도 CDN 에서 받아오므로 같이 넣는다.

셋 다 `window` 에 이미 있으면 받지 않고 넘어가도록 되어 있다. 그래서
`support.js` 보다 먼저 실행되게 `<head>` 맨 앞에 두면 그것으로 끝난다.

## 주소와 무결성 값

`design/runtime/support.js` 가 적어 둔 주소와 SRI 가 아래와 같다. 받을 때
이 값과 맞는지 확인했다. support.js 를 새로 받으면 버전이 올라갔을 수
있으니 여기도 같이 맞춰야 한다.

    react@18.3.1        https://unpkg.com/react@18.3.1/umd/react.production.min.js
      sha384-DGyLxAyjq0f9SPpVevD6IgztCFlnMF6oW/XQGmfe+IsZ8TqEiDrcHkMLKI6fiB/Z
    react-dom@18.3.1    https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js
      sha384-gTGxhz21lVGYNMcdJOyq01Edg0jhn/c22nsx0kyqP0TxaV5WVdsSH1fSDUf5YJj1
    @babel/standalone@7.29.0  https://unpkg.com/@babel/standalone@7.29.0/babel.min.js
      sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y

다시 받고 확인하려면

    cd design/runtime/vendor
    curl -sSLO <주소>
    openssl dgst -sha384 -binary <파일> | openssl base64 -A

## Babel 을 미리 돌려서 빼면 안 되나

된다. node 로 미리 바꿔 두고 `from` 을 `.js` 로 바꾸면 3MB 가 빠진다.
그러면 빌드에 node 가 끼고, 화면이 Claude Design 안에서 도는 경로와
달라진다. 거기서 되는 것이 파일에서 안 되는 쪽이 더 비싸다고 보고 같은
경로로 두었다. 파일이 커서 문제가 되면 그때 바꾼다.
