# `witness_dsl` 设计机理讲义

> 教学用。每一节对应 `GRAMMAR.bnf` 里的一条产生式或一条设计决策，
> 用「合法 / 非法」对照来展示这条规则想表达什么，以及它为什么被这样切分。
> 所有代码片段都用 `syntax_check.py` 跑过，报错文本是真实输出。

跑法（在 `c2rust_translation/` 目录下）：

```
python3 -m witness_dsl path/to/file.wit        # 完整报告
python3 -m witness_dsl -q *.wit                # 只报失败
python3 -m witness_dsl --strict file.wit       # 警告也算失败
```

退出码 `0` 当且仅当每个文件都语法合法。

---

## 0. 一句话哲学

这个 DSL 的前端**只回答一个问题**：

> 这个文件符合 `GRAMMAR.bnf` 吗？

它不解析名字、不查类型、不解释语义。`original.m` 是不是真的存在、`m[:]`
是不是真的作用在 map 上、`bpf_map_update_elem` 是不是真的有 `flags` 参数
—— 这些全部交给后面的语义层（`lower.py`）。

**教学要点**：语法层与语义层的边界画在哪里，是 DSL 设计里最重要的一个决定。
下面每一节的「故意宽松」标记，都是这条边界的体现。

---

## 1. 程序 = 三段式，顺序固定，前两段可选可空

```bnf
<program> ::= <opt-assumption-block> <opt-binding-block> <observation-block>

<opt-assumption-block> ::= <assumption-block> | ε
<opt-binding-block>    ::= <binding-block>    | ε
```

> 设计决策 (4)：`assumption` 和 `binding` 可以缺省、也可以为空块；
> `observation` 必须出现，且至少一条语句。

机理：一个 witness 的**核心断言**是「优化前后要观察到什么相等」，所以
`observation` 是唯一的必需部分。前提（`assumption`）和对应关系（`binding`）
是可选的松弛条件——没有它们，检查只会更严格，不会不成立。

### 1.1 最小合法程序

```wit
observation {
    original.return = optimized.return;
}
```

```
=> OK
```

### 1.2 前两段出现但为空 —— 合法

```wit
assumption {
}
binding {
}
observation {
    original.return = optimized.return;
}
```

```
=> OK
```

### 1.3 块顺序颠倒 —— 非法

```wit
binding {
}
assumption {
}
observation {
    original.return = optimized.return;
}
```

```
error: keyword 'assumption' block is out of order or repeated; blocks must
appear as: assumption? binding? observation (each at most once)
  |
3 | assumption {
  | ^^^^^^^^^^
```

顺序写死在产生式里（不是用集合），所以「顺序错」和「重复」是同一条错误。

### 1.4 同一个块出现两次 —— 非法

```wit
observation {
    original.a = optimized.a;
}
observation {
    original.b = optimized.b;
}
```

```
error: expected end of input after the observation block, found keyword 'observation'
```

### 1.5 缺少 `observation` —— 非法

```wit
assumption {
    ignore flag of h;
}
```

```
error: expected the 'observation' block, found end of input
```

### 1.6 `observation` 为空 —— 非法

```wit
observation {
}
```

```
error: the 'observation' block must contain at least one statement
```

注意这条规则**无法**只靠 BNF 表达（`<observation-list>` 至少一项是能写的，
但「块里必须非空」这种结构约束仍由检查器显式兜底）。

---

## 2. `;` 是语句终结符，永远必需

```bnf
<assumption-statement>  ::= <range-assumption>  ";" | <ignore-assumption> ";"
<binding-statement>     ::= <original-expression> "=" <optimized-expression> ";"
<observation-statement> ::= <original-expression> "=" <optimized-expression> ";"
```

> 设计决策 (9)：`;` 是终结符，任何时候都要写。

```wit
observation {
    original.return = optimized.return
}
```

```
error: expected ';', found '}'
  |
3 | }
  | ^
```

机理：不做「行尾即语句尾」这种隐式规则，换来的是——多行表达式、注释穿插
都不会改变语句边界。代价是每条都要打分号。

---

## 3. `=` 两侧写死为 `original.` = `optimized.`

```bnf
<binding-statement>     ::= <original-expression> "=" <optimized-expression> ";"
<observation-statement> ::= <original-expression> "=" <optimized-expression> ";"

<original-expression>  ::= "original"  "." <expression>
<optimized-expression> ::= "optimized" "." <expression>
```

左边**只能**是 `original.`，右边**只能**是 `optimized.`。

```wit
observation {
    optimized.return = original.return;
}
```

```
error: the left-hand side of a statement in the observation block must be an
'original.' expression, found 'optimized.'
```

机理：witness 描述的是一个**有方向**的变换（original → optimized）。
把方向固定进语法，就不用在语义层再消歧「这条等式哪边是基准」。

---

## 4. 表达式 = 变量 + accessor 链（故意宽松）

```bnf
<expression>    ::= <variable> <accessor-list>
<accessor-list> ::= ε | <accessor> <accessor-list>
<accessor>      ::= "[:]" | "[" <variable> "]" | "." <field-name>
```

> 设计决策 (6)：表达式是「变量 + 一串取用」，所以 `m[k].a.b`、`m[:].v`
> 这种嵌套访问天然可写。语法**故意宽松**：`x[:][:]`、`scalar.f` 也能过。
> 类型一致性留给语义层，不在这个检查器里。

### 4.1 嵌套访问 —— 合法

```wit
observation {
    original.m[k].a.b = optimized.m[k].a.b;
    original.m[:].v   = optimized.m[:].v;
}
```

```
=> OK
```

三种 accessor 可以任意串联：`[:]`（对整个 map 的所有 key）、`[k]`（用某个
变量当 key）、`.field`（取结构体字段）。

### 4.2 明显「类型不对」的写法 —— 语法层照样放行

```wit
observation {
    original.x[:][:]  = optimized.x[:][:];
    original.scalar.f = optimized.scalar.f;
}
```

```
=> OK
```

`x[:][:]`（对 map 迭代两次）、`scalar.f`（对标量取字段）在语义上都是错的，
但**语法层不管**。它们会在 `lower.py` 的 kind 检查里被拒。

**教学要点**：宽松的语法 + 独立的语义层，比「把所有约束塞进语法」更好维护——
BNF 保持小而稳定，类型规则可以单独演进。

---

## 5. `[:]` 是一个不可分割的 token

> 词法侧条件 L4：`[:]` 是单个 token，`[` `:` `]` 之间不允许有空白。
> L6：最长匹配（maximal munch），词法器每步吃掉最长的合法 token。

```wit
observation {
    original.m[ : ].v = optimized.m[ : ].v;
}
```

```
error: unexpected character ':'
  |
2 |     original.m[ : ].v = optimized.m[ : ].v;
  |                 ^
```

机理：`[` 后面紧跟 `:` 才被识别为「遍历所有 key」；一旦有空格，`[` 就走
`[` `<variable>` `]` 那条产生式，而 `:` 不是合法变量，于是报「意外字符」。
把 `[:]` 做成原子 token，避免了 `[` 之后要 lookahead 才能决定走哪条规则。

---

## 6. 整数：可负、可十六进制、十进制不许前导零

```bnf
<number>          ::= <unsigned-number> | "-" <unsigned-number>
<unsigned-number> ::= <decimal> | <hex>
<decimal>         ::= "0" | <nonzero-digit> <digit-list>
<hex>             ::= "0x" <hex-digit> <hex-digit-list>
```

> 设计决策 (5)：整数可带前导 `-`，可写十六进制（`0x...`）；
> 十进制字面量不许前导零。
> 词法侧条件 L5：`01`、`007` 是词法错误；`0x` 后面没有 hex 位也是词法错误。

### 6.1 合法

```wit
assumption {
    original.x in [-1, 0x7fffffff];
    optimized.y in [0, 255];
}
observation { original.return = optimized.return; }
```

```
=> OK
```

### 6.2 前导零 —— 非法

```wit
assumption {
    original.x in [0, 007];
}
```

```
error: decimal literal may not have a leading zero
  |
2 |     original.x in [0, 007];
  |                       ^^^
```

机理：前导零在很多语言里意味着八进制。这里直接禁掉，消除「`010` 是 8 还是
10」的歧义，也逼迫作者写清楚意图。

### 6.3 `0x` 后无 hex 位 —— 非法

```wit
assumption {
    original.x in [0, 0x];
}
```

```
error: hexadecimal literal has no digits after '0x'
```

---

## 7. `range` 假设可以约束任意一侧

```bnf
<range-assumption> ::= <side-expression> "in" "[" <number> "," <number> "]"
<side-expression>  ::= <original-expression> | <optimized-expression>
```

> 设计决策 (7)：range 假设可以指向 `original.` 或 `optimized.` 任意一侧。

```wit
assumption {
    optimized.cfg[key].rate in [-1, 0x7fffffff];
}
observation { original.return = optimized.return; }
```

```
=> OK
```

对比第 3 节：`observation` / `binding` 的 `=` 两侧写死，但 `range` 不写死。
机理——前提条件既可能是「原程序的某个输入在某范围内」，也可能是「优化程序
里某个被收窄的量在某范围内」，两种都有意义，所以这里保留 `<side-expression>`
的二选一。

注意 range 的 `<side-expression>` 前缀也是必需的：

```wit
assumption {
    x in [0, 10];
}
```

```
error: expected 'original.' or 'optimized.', found identifier 'x'
```

---

## 8. `ignore flag of <helper>` 是写死的固定形，不做泛化

```bnf
<ignore-assumption> ::= "ignore" "flag" "of" <helper-name>
```

> 设计决策 (8)：`ignore` 固定成 `ignore flag of <helper-name>`，不泛化。

### 8.1 合法

```wit
assumption {
    ignore flag of bpf_map_update_elem;
}
observation { original.return = optimized.return; }
```

```
=> OK
```

语义：把某个 helper 的 `flags` 实参抽象掉，让 Heimdall 对所有 flag 取值建模
这个 helper。

### 8.2 换个词 —— 非法

```wit
assumption {
    ignore flags of bpf_map_update_elem;
}
```

```
error: expected keyword 'flag', found identifier 'flags'
  |
2 |     ignore flags of bpf_map_update_elem;
  |            ^^^^^
```

机理：目前只有这一种「忽略」需求。与其设计一套通用的「忽略 X 的 Y」语法，
不如先固定成一句话——等真的出现第二种需求再泛化。**DSL 应该按需生长，
不要提前造框架。**

---

## 9. 保留字不能当标识符

> 词法侧条件 L3：下列词**不是**合法 `<identifier>`：
> `assumption  binding  observation  in  ignore  flag  of  original  optimized`
> 因此变量 / 字段 / helper 名都不能正好是其中之一。

### 9.1 用 `flag` 当字段名 —— 非法

```wit
observation {
    original.ctx.flag = optimized.ctx.flag;
}
```

```
error: expected a field name, found keyword 'flag'
  |
2 |     original.ctx.flag = optimized.ctx.flag;
  |                  ^^^^
```

### 9.2 只是「以保留字开头」—— 合法

```wit
observation {
    original.informant = optimized.informant;
    original.flagship  = optimized.flagship;
}
```

```
=> OK
```

`in`、`flag` 是整词保留，`informant` / `flagship` 只是碰巧前缀相同，最长匹配
会把它们当成完整标识符。

### 9.3 `return` 不是保留字，但也不能裸写

```wit
observation {
    return = optimized.return;
}
```

```
error: expected 'original.' or 'optimized.', found identifier 'return'
```

`return` 在 L3 列表之外，所以它是**合法标识符**（可以当字段名，见各例里的
`original.return`）。这里报错是因为语句左边缺 `original.` 前缀（第 3 节），
不是因为 `return` 本身。

**教学要点**：区分「这个词被保留了」和「这个位置需要别的东西」——两种错误
的修法完全不同。

### 已知局限

如果哪天真有一个 BPF 结构体字段就叫 `flag` 或 `of`，这套关键字就得改成
**上下文相关关键字**（只在特定位置才当关键字）。当前实现没做这一步。

---

## 10. 注释等价于空白

> 词法侧条件 L2：
> 行注释 `// ...` 到行尾；块注释 `/* ... */` 到下一个 `*/`（不嵌套）。
> 未闭合的块注释是词法错误。

### 10.1 各种位置的注释 —— 合法

```wit
// line comment
observation {
    /* block */ original.return = optimized.return; // trailing
}
```

```
=> OK
```

注释可以插在 token 之间任何地方，因为它在词法层就被当成空白吃掉了。

### 10.2 未闭合块注释 —— 非法

```wit
observation {
    original.return = optimized.return;
} /* oops
```

```
error: unterminated block comment
  |
3 | } /* oops
  |   ^^
```

块注释不嵌套（`/* /* */` 在第一个 `*/` 就结束），这样词法器不用维护
计数器，实现简单、行为可预测。

---

## 11. 可选的「良构性」警告

这些不是语法错误——文件仍然合法——但多半是笔误。默认会打印，
`--no-extra` 跳过，`--strict` 让它们导致失败。

### 11.1 空区间 `[lo > hi]`

```wit
assumption {
    original.x in [10, 0];
}
observation { original.return = optimized.return; }
```

```
warning: empty range [10, 0]: lower bound exceeds upper bound
=> OK (1 warning)          # 加 --strict 则 FAILED
```

### 11.2 重复的 `ignore flag of X`

```wit
assumption {
    ignore flag of h;
    ignore flag of h;
}
observation { original.return = optimized.return; }
```

```
warning: duplicate 'ignore flag of h'
```

### 11.3 完全相同的 binding / observation 语句重复

```wit
observation {
    original.return = optimized.return;
    original.return = optimized.return;
}
```

```
warning: duplicate observation statement 'original.return = optimized.return'
```

机理：语法层严格「对 / 错」，良构性警告是叠在上面的一层**可关闭的**提示。
把两者分开，工具在不同场景（快速实验 vs. CI 门禁）可以调不同的严格度。

---

## 12. 语法层**不**做的事（留给 `lower.py`）

| 问题 | 谁来管 |
|---|---|
| `original.m` 是不是原程序里真实的变量 / map？ | 语义层 |
| `m[:]` 用在 map 上、`.f` 用在结构体上了吗？（`x[:][:]`、`scalar.f` 语法过） | 语义层 kind 检查 |
| `bpf_map_update_elem` 真的有 `flags` 参数吗？ | 语义层 |
| 把三个块下降成一个关系证明义务 | 语义层 |

一句话总结整份讲义：**BNF 负责形状，语义层负责意义，中间那条线画在
「不看具体程序就能判定的」和「必须看程序才能判定的」之间。**
