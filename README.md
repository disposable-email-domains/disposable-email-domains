List of disposable email domains
========================

[![Licensed under CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/)

This repo contains a [list of disposable and temporary email address domains](disposable_email_blocklist.conf) often used to register dummy users in order to spam or abuse some services.

We cannot guarantee all of these can still be considered disposable but we do basic checking so chances are they were disposable at one point in time.

Allowlist
=========
The file [allowlist.conf](allowlist.conf) gathers email domains that are often identified as disposable but in fact are not.

Example Usage
=============
**Python**
```Python
blocklist = ('disposable_email_blocklist.conf')
blocklist_content = [line.rstrip() for line in blocklist.readlines()]
if email.split('@')[1] in blocklist_content:
    message = "Please enter your permanent email address."
    return (False, message)
else:
    return True
```

Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)
```python
>>> from disposable_email_domains import blocklist
>>> 'bearsarefuzzy.com' in blocklist
True
```

**PHP** contributed by [@txt3rob](https://github.com/txt3rob), [@deguif](https://github.com/deguif), [@pjebs](https://github.com/pjebs) and [@Wruczek](https://github.com/Wruczek)

1. Make sure the passed email is valid. You can check that with [filter_var](https://secure.php.net/manual/en/function.filter-var.php)
2. Make sure you have the mbstring extension installed on your server
```php
function isDisposableEmail($email, $blocklist_path = null) {
    if (!$blocklist_path) $blocklist_path = __DIR__ . '/disposable_email_blocklist.conf';
    $disposable_domains = file($blocklist_path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    $domain = mb_strtolower(explode('@', trim($email))[1]);
    return in_array($domain, $disposable_domains);
}
```
**Ruby on Rails** contributed by [@MitsunChieh](https://github.com/MitsunChieh)

In resource model, usually it is `user.rb`
```Ruby
before_validation :reject_email_blocklist

def reject_email_blocklist
  blocklist = File.read('config/disposable_email_blocklist.conf').split("\n")

  if blocklist.include?(email.split('@')[1])
    errors[:email] << 'invalid email'
    return false
  else
    return true
  end
end
```
**NodeJs** contributed by [@martin-fogelman](https://github.com/martin-fogelman)

```Node
'use strict';

const readline = require('readline'),
  fs = require('fs');

const input = fs.createReadStream('./disposable_email_blocklist.conf'),
  output = [],
  rl = readline.createInterface({input});

// PROCESS LINES
rl.on('line', (line) => {
  console.log(`Processing line ${output.length}`);
  output.push(line);
});

// SAVE AS JSON
rl.on('close', () => {
  try {
    const json = JSON.stringify(output);
    fs.writeFile('disposable_email_blocklist.json', json, () => console.log('--- FINISHED ---'));
  } catch (e) {
    console.log(e);
  }
});
```

**C#**
```C#
private static readonly Lazy<HashSet<string>> _emailBlockList = new Lazy<HashSet<string>>(() =>
{
  var lines = File.ReadLines("disposable_email_blocklist.conf")
    .Where(line => !string.IsNullOrWhiteSpace(line) && !line.TrimStart().StartsWith("//"));
  return new HashSet<string>(lines, StringComparer.OrdinalIgnoreCase);
});

private static bool IsBlocklisted(string domain) => _emailBlockList.Value.Contains(domain);

...

var addr = new MailAddress(email);
if (IsBlocklisted(addr.Host)))
  throw new ApplicationException("Email is blocklisted.");
```

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

Specifically, if adding more than one new domain, please cite in your PR where one can generate a disposable email address which uses that domain, so the maintainers can verify it.

Please add new disposable domains directly into [disposable_email_blocklist.conf](disposable_email_blocklist.conf) in the same format (only second level domains on new line without @), then run [maintain.sh](maintain.sh). The shell script will help you convert uppercase to lowercase, sort, remove duplicates and remove allowlisted domains.

Changelog
============

* 2/11/21 We created a github [org account](https://github.com/disposable-email-domains) and transferred the repository to it.

* 4/18/19 [@di](https://github.com/di) [joined](https://github.com/martenson/disposable-email-domains/issues/205) as a core maintainer of this project. Thank you!

* 7/31/17 [@deguif](https://github.com/deguif) [joined](https://github.com/martenson/disposable-email-domains/issues/106) as a core maintainer of this project. Thanks!

* 12/6/16 - Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)

* 7/27/16 - Converted all domains to the second level. This means that starting from [this commit](https://github.com/martenson/disposable-email-domains/commit/61ae67aacdab0b19098de2e13069d7c35b74017a) the implementers should take care of matching the second level domain names properly i.e. `@xxx.yyy.zzz` should match `yyy.zzz` in blocklist more info in [#46](https://github.com/martenson/disposable-email-domains/issues/46)
