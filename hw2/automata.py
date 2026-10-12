from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import FrozenSet

EPS = None

@dataclass
class NFA:
    start: int
    accepts: dict[int, tuple[str, int]]   # state -> (token, priority)
    trans: dict[int, dict[str | None, set[int]]]
    states: set[int]
    next_state: int
    alphabet: set[str]

    def add_transition(self, src, symbol, dst):
        self.trans.setdefault(src, {}).setdefault(symbol, set()).add(dst)
        if symbol is not None:
            self.alphabet.add(symbol)

class NFABuilder:
    def __init__(self):
        self.next_state = 0
        self.trans = defaultdict(lambda: defaultdict(set))
        self.alphabet = set()

    def state(self):
        s = self.next_state
        self.next_state += 1
        return s

    def edge(self, a, sym, b):
        self.trans[a][sym].add(b)
        if sym is not None:
            self.alphabet.add(sym)

    def literal(self, ch):
        a, b = self.state(), self.state()
        self.edge(a, ch, b)
        return a, b

    def epsilon(self):
        a, b = self.state(), self.state()
        self.edge(a, None, b)
        return a, b

    def concat(self, x, y):
        self.edge(x[1], None, y[0])
        return x[0], y[1]

    def union(self, x, y):
        a, b = self.state(), self.state()
        self.edge(a, None, x[0]); self.edge(a, None, y[0])
        self.edge(x[1], None, b); self.edge(y[1], None, b)
        return a, b

    def star(self, x):
        a, b = self.state(), self.state()
        self.edge(a, None, b)
        self.edge(a, None, x[0])
        self.edge(x[1], None, x[0])
        self.edge(x[1], None, b)
        return a, b

    def plus(self, x):
        a, b = self.state(), self.state()
        self.edge(a, None, x[0])
        self.edge(x[1], None, x[0])
        self.edge(x[1], None, b)
        return a, b

    def optional(self, x):
        a, b = self.state(), self.state()
        self.edge(a, None, x[0]); self.edge(a, None, b)
        self.edge(x[1], None, b)
        return a, b

# ---------- Regex parser ----------
# Supported:
#   |, implicit concatenation, *, +, ?, (), [] character classes,
#   ranges a-z, escaped literals (\+, \[, \\, \t, \r, \n, \s).
# Dot is not needed by the assignment and is deliberately unsupported.

def parse_escape(s, i):
    assert s[i] == "\\"
    if i + 1 >= len(s):
        raise ValueError("dangling escape")
    c = s[i + 1]
    table = {"n":"\n", "r":"\r", "t":"\t", "f":"\f", "v":"\v", "0":"\0"}
    return table.get(c, c), i + 2

def parse_class(s, i):
    # i points at '['; returns (set(chars), new_index)
    i += 1
    if i >= len(s):
        raise ValueError("unterminated character class")
    neg = False
    if s[i] == "^":
        neg = True
        i += 1
    chars = set()
    while i < len(s) and s[i] != "]":
        if s[i] == "\\":
            c, i = parse_escape(s, i)
        else:
            c, i = s[i], i + 1

        # range if '-' follows and there is a non-] endpoint
        if i < len(s) - 1 and s[i] == "-" and s[i + 1] != "]":
            i += 1
            if s[i] == "\\":
                d, i = parse_escape(s, i)
            else:
                d, i = s[i], i + 1
            if ord(c) > ord(d):
                raise ValueError(f"bad range {c}-{d}")
            chars.update(chr(x) for x in range(ord(c), ord(d) + 1))
        else:
            chars.add(c)
    if i >= len(s) or s[i] != "]":
        raise ValueError("unterminated character class")
    if neg:
        chars = {chr(x) for x in range(128)} - chars
    return chars, i + 1

class RegexParser:
    def __init__(self, text, builder):
        self.s = text
        self.b = builder
        self.i = 0

    def parse(self):
        frag = self.expr()
        if self.i != len(self.s):
            raise ValueError(f"unexpected character at {self.i}: {self.s[self.i]!r}")
        return frag

    def expr(self):
        left = self.concat_expr()
        while self.i < len(self.s) and self.s[self.i] == "|":
            self.i += 1
            right = self.concat_expr()
            left = self.b.union(left, right)
        return left

    def concat_expr(self):
        parts = []
        while self.i < len(self.s) and self.s[self.i] not in ")|":
            parts.append(self.factor())
        if not parts:
            return self.b.epsilon()
        out = parts[0]
        for p in parts[1:]:
            out = self.b.concat(out, p)
        return out

    def factor(self):
        atom = self.atom()
        while self.i < len(self.s) and self.s[self.i] in "*+?":
            op = self.s[self.i]; self.i += 1
            if op == "*": atom = self.b.star(atom)
            elif op == "+": atom = self.b.plus(atom)
            else: atom = self.b.optional(atom)
        return atom

    def atom(self):
        if self.i >= len(self.s):
            raise ValueError("expected atom")
        c = self.s[self.i]
        if c == "(":
            self.i += 1
            x = self.expr()
            if self.i >= len(self.s) or self.s[self.i] != ")":
                raise ValueError("missing ')'")
            self.i += 1
            return x
        if c == "[":
            chars, self.i = parse_class(self.s, self.i)
            return self.class_fragment(chars)
        if c == "\\":
            ch, self.i = parse_escape(self.s, self.i)
            return self.b.literal(ch)
        if c in "*+?)|":
            raise ValueError(f"unexpected regex operator {c!r}")
        self.i += 1
        return self.b.literal(c)

    def class_fragment(self, chars):
        if not chars:
            raise ValueError("empty character class")
        frags = [self.b.literal(c) for c in sorted(chars)]
        out = frags[0]
        for f in frags[1:]:
            out = self.b.union(out, f)
        return out

def build_combined_nfa(rules):
    b = NFABuilder()
    start = b.state()
    accepts = {}
    for priority, (token, regex, skip) in enumerate(rules):
        frag = RegexParser(regex, b).parse()
        b.edge(start, None, frag[0])
        accepts[frag[1]] = (token, priority, skip)
    return NFA(start, accepts, {k: dict(v) for k,v in b.trans.items()},
               set(range(b.next_state)), b.next_state, b.alphabet)

def epsilon_closure(nfa, states):
    out = set(states)
    stack = list(states)
    while stack:
        s = stack.pop()
        for t in nfa.trans.get(s, {}).get(None, ()):
            if t not in out:
                out.add(t); stack.append(t)
    return frozenset(out)

def move(nfa, states, symbol):
    out = set()
    for s in states:
        out.update(nfa.trans.get(s, {}).get(symbol, ()))
    return out

@dataclass
class DFA:
    alphabet: tuple[str, ...]
    start: int
    trans: dict[int, dict[str, int]]
    accepting: dict[int, tuple[str, int, bool]]
    states: set[int]

    def run(self, text):
        q = self.start
        for ch in text:
            if ch not in self.trans.get(q, {}):
                return None
            q = self.trans[q][ch]
        return self.accepting.get(q)

    def accepts(self, text):
        return self.run(text) is not None

def nfa_to_dfa(nfa, alphabet):
    start_set = epsilon_closure(nfa, [nfa.start])
    ids = {start_set: 0}
    sets = [start_set]
    trans = {}
    accepting = {}
    queue = deque([start_set])

    while queue:
        S = queue.popleft()
        sid = ids[S]
        trans[sid] = {}
        candidates = []
        for st in S:
            if st in nfa.accepts:
                candidates.append(nfa.accepts[st])
        if candidates:
            accepting[sid] = min(candidates, key=lambda x: x[1])

        for ch in alphabet:
            Traw = move(nfa, S, ch)
            if not Traw:
                continue
            T = epsilon_closure(nfa, Traw)
            if T not in ids:
                ids[T] = len(ids)
                sets.append(T)
                queue.append(T)
            trans[sid][ch] = ids[T]

    return DFA(tuple(alphabet), 0, trans, accepting, set(trans))

def complete_dfa(dfa):
    trans = {q: dict(row) for q, row in dfa.trans.items()}
    states = set(dfa.states)
    trap = max(states, default=-1) + 1
    need_trap = False
    for q in list(states):
        for a in dfa.alphabet:
            if a not in trans[q]:
                trans[q][a] = trap
                need_trap = True
    if need_trap:
        states.add(trap)
        trans[trap] = {a: trap for a in dfa.alphabet}
    return DFA(dfa.alphabet, dfa.start, trans, dict(dfa.accepting), states)

def reachable(dfa):
    seen = {dfa.start}
    todo = [dfa.start]
    while todo:
        q = todo.pop()
        for t in dfa.trans.get(q, {}).values():
            if t not in seen:
                seen.add(t); todo.append(t)
    return seen

def trim_unreachable(dfa):
    keep = reachable(dfa)
    trans = {q: {a:t for a,t in row.items() if t in keep} for q,row in dfa.trans.items() if q in keep}
    acc = {q:v for q,v in dfa.accepting.items() if q in keep}
    return DFA(dfa.alphabet, dfa.start, trans, acc, keep)

def hopcroft_minimize(dfa):
    dfa = trim_unreachable(complete_dfa(dfa))
    Q = set(dfa.states)
    # This is a token-labelled DFA, not just a recognizer for the union
    # of all token languages. Accepting states with different token metadata
    # must NOT be merged: otherwise FUNCTION, IDENT, INT, etc. would lose
    # their token kind after minimization. Therefore the initial partition
    # is by exact accepting metadata, plus one non-accepting block.
    groups = {}
    for q in Q:
        key = ("A", dfa.accepting[q]) if q in dfa.accepting else ("N",)
        groups.setdefault(key, set()).add(q)
    P = list(groups.values())
    W = P.copy()

    while W:
        A = W.pop()
        for c in dfa.alphabet:
            X = {q for q in Q if dfa.trans[q][c] in A}
            newP = []
            for Y in P:
                inter = Y & X
                diff = Y - X
                if inter and diff:
                    newP.extend([inter, diff])
                    if Y in W:
                        W.remove(Y)
                        W.extend([inter, diff])
                    else:
                        W.append(inter if len(inter) <= len(diff) else diff)
                else:
                    newP.append(Y)
            P = newP

    block_of = {}
    for i, block in enumerate(P):
        for q in block:
            block_of[q] = i

    start = block_of[dfa.start]
    trans = {}
    acc = {}
    for i, block in enumerate(P):
        rep = next(iter(block))
        trans[i] = {a: block_of[dfa.trans[rep][a]] for a in dfa.alphabet}
        if any(q in dfa.accepting for q in block):
            # All states in a block have the same accepting metadata after
            # partitioning by acceptance. Choose the highest-priority rule.
            metas = [dfa.accepting[q] for q in block if q in dfa.accepting]
            acc[i] = min(metas, key=lambda x: x[1])
    return DFA(dfa.alphabet, start, trans, acc, set(range(len(P))))

def serialize_dfa(dfa):
    return {
        "alphabet": [ord(c) for c in dfa.alphabet],
        "start_state": dfa.start,
        "states": sorted(dfa.states),
        "accepting": {str(q): {"token": m[0], "priority": m[1], "skip": m[2]}
                      for q,m in sorted(dfa.accepting.items())},
        "transitions": {str(q): {str(ord(a)): t for a,t in sorted(row.items())}
                        for q,row in sorted(dfa.trans.items())},
    }

def scan(dfa, text):
    # Maximal munch. If several rules accept the same maximal lexeme,
    # the DFA state stores the lowest rule priority.
    out = []
    i = 0
    while i < len(text):
        q = dfa.start
        j = i
        last = None
        while j < len(text) and text[j] in dfa.trans[q]:
            q = dfa.trans[q][text[j]]
            j += 1
            if q in dfa.accepting:
                last = (j, dfa.accepting[q])
        if last is None:
            out.append({"error": text[i], "position": i})
            i += 1
            continue
        end, meta = last
        token, priority, skip = meta
        lexeme = text[i:end]
        if not skip:
            out.append({"kind": token, "lexeme": lexeme})
        i = end
    return out
