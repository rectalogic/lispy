# Lispy

[![Actions Status](https://github.com/rectalogic/lispy/workflows/Test/badge.svg)](https://github.com/rectalogic/lispy/actions)

Lisp based Python extension language, originally derived from Peter Norvigs [lispy](https://norvig.com/lispy2.html),
but now a fork of [mal (Make-A-Lisp) python.2](https://github.com/kanaka/mal#python2-3x)
(forked from [this commit](https://github.com/kanaka/mal/tree/0279f85f3582f995a69ef5aec3efea1d765ad0f2/python.2))
Refactored into a `Lispy` class to contain all interpreter state.
Also added the ability to expose a restricted subset of python methods and properties into the interpreter.

```pycon
>>> import lispy
>>> from urllib.parse import urlparse, ParseResult
>>> l = lispy.Lispy(injections={"urlparse": urlparse}, restrictions={ParseResult: {"scheme", "netloc", "path"}})
>>> l.repl()
Mal [python.lispy]
user> (def! u (urlparse "https://github.com/rectalogic/lispy"))
"ParseResult(scheme='https', netloc='github.com', path='/rectalogic/lispy', params='', query='', fragment='')"
user> (. u 'path)
"'/rectalogic/lispy'"
user> (. u 'netloc)
"'github.com'"
user> (. u 'query)
ERROR: "\"ParseResult(scheme='https', netloc='github.com', path='/rectalogic/lispy', params='', query='', fragment='')\": invalid argument: Access restricted to attribute \"query\""
user> ($ u)
("'https'" "'github.com'" "'/rectalogic/lispy'" "''" "''" "''")
user> (nth ($ u) 2)
"'/rectalogic/lispy'"
```