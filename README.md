# Lispy

[![Build Status](https://travis-ci.org/rectalogic/lispy.svg?branch=master)](https://travis-ci.org/rectalogic/lispy)

Scheme based Python extension language, derived from Peter Norvigs [lispy](https://norvig.com/lispy2.html).
Ported to Python 3 and refactored into a class to contain all interpreter state.
Also added the ability to expose a restricted subset of python methods and properties into scheme.

```pycon
>>> import lispy
>>> from urllib.parse import urlparse, ParseResult
>>> l = lispy.Lispy(env=lispy.Env(urlparse=urlparse), dotaccess={ParseResult: {"scheme", "netloc", "path"}})
>>> l.repl()
Lispy version 2.0
lispy> (define u (urlparse "https://github.com/rectalogic/lispy"))
lispy> u
ParseResult(scheme='https', netloc='github.com', path='/rectalogic/lispy', params='', query='', fragment='')
lispy> (. u 'path)
"/rectalogic/lispy"
lispy> (. u 'netloc)
"github.com"
```