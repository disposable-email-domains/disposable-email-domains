List of disposable email domains
========================

[![Licensed under CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/)

This repo contains a [list of disposable and temporary email address domains](disposable_email_blacklist.conf) often used to register dummy users in order to spam/abuse some services. 

Originally collected to filter new user registration at https://usegalaxy.org and later merged with other lists found online. I cannot guarantee all of these can still be considered disposable but they probably were at one point in time.

Whitelist
=========
The file [whitelist.conf](whitelist.conf) gathers email domains that are often identified as disposable but in fact are not.

Example Usage
=============
**Python**
```Python
blacklist = ('disposable_email_blacklist.conf')
blacklist_content = [line.rstrip() for line in blacklist.readlines()]
if email.split('@')[1] in blacklist_content:
    message = "Please enter your permanent email address."
    return (False, message)
else:
    return True
```

Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)
```python
>>> from disposable_email_domains import blacklist
>>> 'bearsarefuzzy.com' in blacklist
True
```

**PHP** contributed by [@txt3rob](https://github.com/txt3rob), [@deguif](https://github.com/deguif) and [@pjebs](https://github.com/pjebs)
```php
function is_disposable_email($email) {
  $path = realpath(dirname(__FILE__)) . '/disposable_email_blacklist.conf';
  $mail_domains_ko = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
  $mail_domains_ko = array_fill_keys($mail_domains_ko, true);
  $domain = mb_strtolower(explode('@', trim($email))[1]);
  return (isset($mail_domains_ko[$domain]) || array_key_exists($domain, $mail_domains_ko));
}
```
**Ruby on Rails** contributed by [@MitsunChieh](https://github.com/MitsunChieh)

In resource model, usually it is `user.rb`
```Ruby
before_validation :reject_email_blacklist

def reject_email_blacklist
  blacklist = File.read('config/disposable_email_blacklist.conf').split("\n")

  if blacklist.include?(email.split('@')[1])
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

const input = fs.createReadStream('./disposable_email_blacklist.conf'),
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
    fs.writeFile('disposable_email_blacklist.json', json, () => console.log('--- FINISHED ---'));
  } catch (e) {
    console.log(e);
  }
});
```

**C#**
```C#
private static readonly Lazy<HashSet<string>> _emailBlackList = new Lazy<HashSet<string>>(() =>
{ 
  var lines = File.ReadLines("disposable_email_blacklist.conf")
    .Where(line => !string.IsNullOrWhiteSpace(line) && !line.TrimStart().StartsWith("//"));
  return new HashSet<string>(lines, StringComparer.OrdinalIgnoreCase);
});

private static bool IsBlacklisted(string domain) => _emailBlackList.Value.Contains(domain);

...

var addr = new MailAddress(email);
if (IsBlacklisted(addr.Host)))
  throw new ApplicationException("Email is blacklisted.");
```

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

Use 

`$ cat disposable_email_blacklist.conf your_file | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i  > new_file.conf`

`$ comm -23 new_file.conf whitelist.conf > disposable_email_blacklist.conf`

to add contents of another file in the same format (only second level domains on new line without @). It also converts uppercase to lowercase, sorts, removes duplicates and removes whitelisted domains.

Changelog
============

* 7/31/17 @deguif [joined](https://github.com/martenson/disposable-email-domains/issues/106) as a core maintainer of this project. Thanks!

* 12/6/16 - Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)

* 7/27/16 - Converted all domains to the second level. This means that starting from [this commit](https://github.com/martenson/disposable-email-domains/commit/61ae67aacdab0b19098de2e13069d7c35b74017a) the implementers should take care of matching the second level domain names properly i.e. `@xxx.yyy.zzz` should match `yyy.zzz` in blacklist more info in [#46](https://github.com/martenson/disposable-email-domains/issues/46)
