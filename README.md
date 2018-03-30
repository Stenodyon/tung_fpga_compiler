# FPGA Compiler
A compiler for my basic FPGA system in TUNG

This project is very heavily inspired from [this article](http://blog.notdot.net/2012/10/Build-your-own-FPGA)

## How to use

This program uses the [Lark library](https://github.com/erezsh/lark) which you can install with
`pip install lark-parser`

Usage:

```bash
python compile.py file
```

## The language

Each slice is declared with 
```
module name {
  /* module definition goes here */
}
```
(Note, there is no comment support yet)

### Functions

You can define up to 2 boolean functions using
```
boolean expression (sync) -> output;
```
The `sync` keyword renders the computation synchronous, the result will only be output after a clock signal and it will hold
until the next clock signal.

An expression can use the following operators:
* Name of a lane (`n0`, `n1`, `w0`, ...) except for `s0` and `s1`
* `~a` logical NOT
* `a | b` logical OR
* `a & b` logical AND
* `a ~= b` logical XOR

The `output` can only be on the east or the south sides

### Routing

East-west and North-south lanes can be connected together using the following syntax:
```
w0 <-> e0
```

### Example: full adder
* `n0` is the carry in
* `s0` is the carry out (connects to the `n0` lane of the southern slice for propagation)
* `w0` is the A input
* `w1` is the B input, however we cannot use another input from the west side.
To remedy this problem, we connect `w1` to `e1` with `w1 <-> e1` and use `e1` as the B input
* `e0` is the output of the adder
```
module adder {
    (w0 ~= n0) ~= e1 -> e0;
    (w0 & n0) | (e1 & (n0 ~= w0)) -> s0;
    w1 <-> e1;
}
```
