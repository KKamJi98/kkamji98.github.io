---
title: JavaScript 데이터 타입
date: 2023-06-26 18:38:55 +0900
author: kkamji
categories: [Programming Language, JavaScript]
tags: [web, javascript, js, gitblog, vscode, gitpage, datatype, javascript-data-type]     # TAG names should always be lowercase
comments: true
# image:
# path: https://github.com/kkamji98/Oxi/assets/72260110/3af8c7c9-cc3a-4fed-84d5-c736bad8ba53
---

# 데이터 타입

---

## 1. TL;DR

- JavaScript의 ECMAScript 언어 타입은 `Undefined`, `Null`, `Boolean`, `String`, `Symbol`, `Number`, `BigInt`, `Object`의 8개다.
- `Object`를 제외한 7개는 원시 값(primitive value)이다. 원시 값은 불변이며, 변수 자체는 다른 값으로 재할당할 수 있다.
- `Number`는 IEEE 754 배정밀도 부동소수점 값이다. 안전한 정수 범위를 넘는 정수는 `BigInt` 또는 문자열을 검토해야 한다.
- `typeof null`이 `"object"`인 것은 오래된 언어 동작이다. `null`의 타입이 객체라는 뜻은 아니다.

---

## 2. 값의 타입과 변수의 타입은 다르다

JavaScript는 동적 타입 언어다. 변수 선언에 타입을 고정하지 않으며, 변수에는 서로 다른 타입의 값을 다시 할당할 수 있다. 정확히 말하면 타입은 변수 자체보다 **현재 값**에 연결된다.

```javascript
let value = 42;       // Number 값
value = "ready";     // String 값
value = true;        // Boolean 값
```

이 유연성은 편리하지만, 외부 입력을 받을 때는 의도하지 않은 형 변환을 만들 수 있다. 경계에서 `typeof`, `Array.isArray()`, 스키마 검증 등으로 값의 형태를 확인하는 습관이 필요하다.

---

## 3. ECMAScript의 8개 언어 타입

ECMAScript 명세는 다음 8개 언어 타입을 정의한다.

| 구분 | 타입 | 대표 값 | 핵심 용도 |
| --- | --- | --- | --- |
| 원시 값 | `undefined` | `undefined` | 값이 할당되지 않음 |
| 원시 값 | `null` | `null` | 의도적으로 비어 있는 값을 나타냄 |
| 원시 값 | `boolean` | `true`, `false` | 참과 거짓 |
| 원시 값 | `string` | `"text"` | 텍스트 |
| 원시 값 | `symbol` | `Symbol("id")` | 충돌하지 않는 속성 키 |
| 원시 값 | `number` | `42`, `3.14` | 일반적인 수치 |
| 원시 값 | `bigint` | `9007199254740993n` | 임의 정밀도 정수 |
| 객체 | `object` | `{}`, `[]`, `new Date()` | 속성과 동작의 묶음 |

함수는 `typeof` 연산자에서 `"function"`을 반환하지만, ECMAScript 언어 타입 표에는 별도 타입이 아니라 호출 가능한 객체로 분류된다.

---

## 4. Number와 BigInt

### 4.1. Number

`Number`는 정수와 부동소수점을 구분하지 않는 IEEE 754 배정밀도 부동소수점 타입이다. 정수는 `Number.MIN_SAFE_INTEGER`부터 `Number.MAX_SAFE_INTEGER`까지 정확하게 표현할 수 있다.

```javascript
console.log(Number.MAX_SAFE_INTEGER); // 9007199254740991
console.log(0.1 + 0.2 === 0.3);       // false
```

두 번째 결과는 0.1과 0.2가 이진 부동소수점으로 정확히 표현되지 않기 때문에 발생한다. 금액처럼 정확한 소수 계산이 필요한 도메인에서는 정수의 최소 단위를 사용하거나 별도 정밀도 전략을 선택해야 한다.

### 4.2. BigInt

`BigInt`는 크기 제한 없이 정수를 표현하는 원시 타입이다. 정수 리터럴 뒤에 `n`을 붙이거나 `BigInt()`로 생성한다. 소수는 표현할 수 없으며, `Number`와 산술 연산에서 자동으로 섞이지 않는다.

```javascript
const orderId = 9007199254740993n;
const incremented = orderId + 1n;

console.log(incremented); // 9007199254740994n
console.log(1n + 1);      // TypeError
```

`BigInt`를 JSON으로 직렬화하거나 외부 API와 주고받을 때도 별도 변환 규칙을 정해야 한다.

---

## 5. String, Boolean, Symbol

`String`은 UTF-16 코드 단위의 순서 있는 열이며 원시 값이다. 문자열 값을 직접 바꾸는 대신 새 문자열을 만들어 변수에 다시 할당한다.

```javascript
const name = "Kim";
const greeting = `Hello, ${name}!`;
```

`Boolean`에는 `true`와 `false`만 있다. 조건문에서 다른 타입도 참 또는 거짓으로 변환될 수 있으므로, 값 자체를 비교해야 하는 경우에는 `===`를 사용한다.

`Symbol`은 각 생성 결과가 고유한 원시 값이다. 객체 속성 키의 이름 충돌을 피해야 할 때 사용할 수 있다.

```javascript
const internalId = Symbol("internalId");
const user = { name: "Kim" };

user[internalId] = 1;
console.log(user[internalId]); // 1
```

---

## 6. undefined, null, object

`undefined`와 `null`은 모두 "값이 없다"는 상황에서 보이지만 의미와 생성 경로가 다르다.

- `undefined`는 초기화하지 않은 변수, 존재하지 않는 속성 접근, 값을 반환하지 않은 함수에서 흔히 얻는다.
- `null`은 개발자가 의도적으로 "값 없음"을 표현할 때 사용하는 값이다.

```javascript
let pending;
const result = null;

console.log(pending);        // undefined
console.log(result);         // null
console.log(typeof result);  // "object"
console.log(result === null); // true
```

`typeof null`의 결과는 역사적 호환성을 위한 예외다. `null`인지 확인할 때는 `value === null`을 사용한다. 배열도 `typeof []`가 `"object"`이므로 배열 판별에는 `Array.isArray(value)`를 사용한다.

객체는 속성의 집합이며 배열, 날짜, 정규식, 함수도 객체와 관련된 값이다. 객체와 배열은 내용 변경이 가능하지만, `const`는 바인딩 재할당만 막는다.

```javascript
const settings = { theme: "light" };
settings.theme = "dark"; // 가능
// settings = {};         // TypeError
```

---

## 7. 자료 범위와 한계

타입의 수와 의미는 ECMAScript 2024 명세를 기준으로 하며, 브라우저나 Node.js의 특정 API 목록은 다루지 않는다. 이 글의 `typeof` 예시는 언어의 기본 동작을 설명하지만, 실제 입력 검증에는 애플리케이션의 데이터 형식과 오류 처리 정책이 추가로 필요하다.

---

## 8. Reference

- [ECMAScript 2024: Data Types and Values](https://tc39.es/ecma262/2024/#sec-ecmascript-data-types-and-values)
- [MDN: JavaScript data types and data structures](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Grammar_and_types#data_structures_and_types)
- [MDN: Number](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number)
- [MDN: BigInt](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt)

<br><br>

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
