List of disposable email domains
========================
This repo contains a [list of disposable and temporary email address domains](disposable_email_blocklist.conf) often used to register dummy users in order to spam or abuse some services.

We cannot guarantee all of these can still be considered disposable but we do basic checking so chances are they were disposable at one point in time.

> One of the most impactful mechanisms we currently have is prohibiting known "throw-away" email domains from creating accounts on the index. We currently use the `disposable-email-domains` list as well as our own internal list to block registration with －or association of － such domains for PyPI accounts.

-- Ee Durbin, PyPI Admin, Director of Infrastructure (PSF) [link](https://blog.pypi.org/posts/2024-06-16-prohibiting-msn-emails/)

Allowlist
=========
The file [allowlist.conf](allowlist.conf) gathers email domains that are often identified as disposable but in fact are not.

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

**Specifically, please cite in your PR where one can generate a disposable email address which uses that domain, so the maintainers can verify it.**

Please add new disposable domains directly into [disposable_email_blocklist.conf](disposable_email_blocklist.conf) in the same format (only second level domains on new line without @, unless they use public suffix, in which case include the 3rd level domain), then run [maintain.sh](maintain.sh). The shell script will help you convert uppercase to lowercase, sort, remove duplicates and remove allowlisted domains.

License
=======
You can copy, modify, distribute and use the work, even for commercial purposes, all without asking permission.

[![Licensed under CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/) 

Changelog
============

* 1/9/25 Enabled [GitHub sponsorhip](https://github.com/sponsors/disposable-email-domains) for this work. Everybody can do it, but currently only one person does it. Send them $2 for a coffee if you care.

* 2/11/21 We created a github [org account](https://github.com/disposable-email-domains) and transferred the repository to it.

* 4/18/19 [@di](https://github.com/di) [joined](https://github.com/martenson/disposable-email-domains/issues/205) as a core maintainer of this project. Thank you!

* 7/31/17 [@deguif](https://github.com/deguif) [joined](https://github.com/martenson/disposable-email-domains/issues/106) as a core maintainer of this project. Thanks!

* 12/6/16 - Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)

* 7/27/16 - Converted all domains to the second level. This means that starting from [this commit](https://github.com/martenson/disposable-email-domains/commit/61ae67aacdab0b19098de2e13069d7c35b74017a) the implementers should take care of matching the second level domain names properly i.e. `@xxx.yyy.zzz` should match `yyy.zzz` in blocklist where `zzz` is a [public suffix](https://publicsuffix.org/). More info in [#46](https://github.com/martenson/disposable-email-domains/issues/46)

* 9/2/14 - First commit [393c21f5](https://github.com/disposable-email-domains/disposable-email-domains/commit/393c21f56b5186f8db7d197b11cf1d7c5490a6f9)
  
Example Usage
=============

TOC: [Python](#python), [PHP](#php), [Go](#go), [Ruby](#ruby), [NodeJS](#nodejs), [C#](#c), [bash](#bash), [Java](#java), [Kotlin](#kotlin), [Swift](#swift), [Elixir](#elixir)

### Python
```Python
with open('disposable_email_blocklist.conf') as blocklist:
    blocklist_content = {line.rstrip() for line in blocklist.readlines()}

domain_parts = email.partition('@')[2].split(".")
for i in range(len(domain_parts) - 1):
    if ".".join(domain_parts[i:]) in blocklist_content:
        message = "Please enter your permanent email address."
        return (False, message)
return True
```

Available as [PyPI module](https://pypi.org/project/disposable-email-domains) thanks to [@di](https://github.com/di)
```python
>>> from disposable_email_domains import blocklist
>>> 'bearsarefuzzy.com' in blocklist
True
```

### PHP

1. Make sure the passed email is valid. You can check that with [filter_var](https://secure.php.net/manual/en/function.filter-var.php)
2. Make sure you have the mbstring extension installed on your server
```php
function isDisposableEmail($email, $blocklist_path = null) {
    if (!$blocklist_path) $blocklist_path = __DIR__ . '/disposable_email_blocklist.conf';
    $disposable_domains = file($blocklist_path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

    // Convert blocklist to associative array for faster lookups
    $blocklist_map = array_flip($disposable_domains);

    $domain = mb_strtolower(explode('@', trim($email))[1]);
    $domain_parts = explode('.', $domain);

    // Check domain and all parent domains (skip checking TLD alone)
    for ($i = 0; $i < count($domain_parts) - 1; $i++) {
        $check_domain = implode('.', array_slice($domain_parts, $i));
        if (isset($blocklist_map[$check_domain])) {
            return true;
        }
    }

    return false;
}
```

Alternatively check out Composer package https://github.com/elliotjreed/disposable-emails-filter-php.

### Go

```go
import ("bufio"; "os"; "strings";)
var disposableList = make(map[string]struct{}, 3500)
func init() {
	f, _ := os.Open("disposable_email_blocklist.conf")
	for scanner := bufio.NewScanner(f); scanner.Scan(); {
		disposableList[scanner.Text()] = struct{}{}
	}
	f.Close()
}

func isDisposableEmail(email string) (disposable bool) {
	domain_parts := strings.Split(strings.Split(email, "@")[1], ".")
	for i := 0; i < len(domain_parts)-1; i++ {
		if _, ok := disposableList[strings.Join(domain_parts[i:], ".")]; ok {
			return true
		}
	}
	return false
}
```

Alternatively check out Go package https://github.com/rocketlaunchr/anti-disposable-email.

### Ruby
```Ruby
BLOCKLIST_CONTENT = File.readlines('disposable_email_blocklist.conf', chomp: true).to_set.freeze

def disposable_email?(email)
  domain_parts = email.split('@')[1].split('.')

  (0...domain_parts.length - 1).each do |i|
    if BLOCKLIST_CONTENT.include?(domain_parts[i..-1].join('.'))
      return true
    end
  end
  false
end
```

### Node.js
```js
const { readFileSync } = require("fs");

const blocklistContent = new Set(
  readFileSync("disposable_email_blocklist.conf", "utf-8")
    .split("\r\n")
    .map((line) => line.trim())
    .slice(0, -1)
);

function isPermanentEmail(email) {
  const domainParts = email.split("@")[1].split(".");
  for (let i = 0; i < domainParts.length - 1; i++) {
    if (blocklistContent.has(domainParts.slice(i).join("."))) {
      const message = "Please enter your permanent email address.";
      return [false, message];
    }
  }

  return [true];
}
```

Alternatively check out NPM package https://github.com/mziyut/disposable-email-domains-js.

### C#
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

### Bash

```sh
#!/bin/bash

# This script checks if an email address is temporary.

# Read blocklist file into a bash array
mapfile -t blocklist < disposable_email_blocklist.conf

email="$1"
domain_part="${email#*@}"

declare -A blocked_domains
for d in "${blocklist[@]}"; do
  blocked_domains["$d"]=1
done
    
# Loop until we're on the last domain level
while [[ "$domain_part" == *.* ]]; do
  if [[ -n "${blocked_domains[$domain_part]:-}" ]]; then
    echo "false:Please enter your permanent email address."
    exit 1
  fi

  # Drop the left-most subdomain and try again (sub.mail.com -> mail.com)
  domain_part="${domain_part#*.}"
done

echo "true:"
exit 0
```

### Java

Code assumes that you have added `disposable_email_blocklist.conf` next to your class as classpath resource.

```Java
private static final Set<String> DISPOSABLE_EMAIL_DOMAINS;

static {
    Set<String> domains = new HashSet<>();
    try (BufferedReader in = new BufferedReader(
            new InputStreamReader(
                EMailChecker.class.getResourceAsStream("disposable_email_blocklist.conf"), StandardCharsets.UTF_8))) {
        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }
            
            domains.add(line);
        }
    } catch (IOException ex) {
        LOG.error("Failed to load list of disposable email domains.", ex);
    }
    DISPOSABLE_EMAIL_DOMAINS = domains;
}

public static boolean isDisposable(String email) throws AddressException {
    InternetAddress contact = new InternetAddress(email);
    return isDisposable(contact);
}

public static boolean isDisposable(InternetAddress contact) throws AddressException {
    String address = contact.getAddress();
    int domainSep = address.indexOf('@');
    String domain = (domainSep >= 0) ? address.substring(domainSep + 1) : address;
    return DISPOSABLE_EMAIL_DOMAINS.contains(domain);
}
```

### Kotlin
contributed by [@nillpoe](https://github.com/nillpoe)

```kotlin
companion object {
    private const val PSL_LIST_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
    private const val DISPOSABLE_LIST_URL = "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/refs/heads/main/disposable_email_blocklist.conf"
}

private val publicSuffixes = mutableSetOf<String>()
private val wildcardSuffixes = mutableSetOf<String>()
private val exceptions = mutableSetOf<String>()

private val disposableEmailDomains = loadDisposableDomains()

init {
    try {
        BufferedReader(InputStreamReader(URI(PSL_LIST_URL).toURL().openStream())).use { reader ->
            reader.lineSequence()
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("//") }
                .forEach {
                    when {
                        it.startsWith("!") -> exceptions.add(it.removePrefix("!"))
                        it.startsWith("*.") -> wildcardSuffixes.add(it.removePrefix("*."))
                        else -> publicSuffixes.add(it)
                    }
                }
        }
    } catch (e: Exception) {
        println("Failed to load PSL: ${e.message}")
    }
}

private fun loadDisposableDomains(): Set<String> {
    val result = mutableSetOf<String>()
    try {
        BufferedReader(InputStreamReader(URI(DISPOSABLE_LIST_URL).toURL().openStream())).use { reader ->
            reader.lineSequence()
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("#") }
                .forEach(result::add)
        }
    } catch (e: Exception) {
        println("Failed to load disposable list: ${e.message}")
    }
    return result
}

fun getRegistrableDomain(domain: String): String? {
    val parts = domain.lowercase().split(".")
    for (i in 0 until parts.size) {
        val candidate = parts.subList(i, parts.size).joinToString(".")

        if (exceptions.contains(candidate)) {
            if (i > 0) {
                return parts.subList(i - 1, parts.size).joinToString(".")
            }
            return null
        }

        if (publicSuffixes.contains(candidate)) {
            if (i > 0) {
                return parts.subList(i - 1, parts.size).joinToString(".")
            }
            return null
        }

        if (wildcardSuffixes.contains(parts.subList(i + 1, parts.size).joinToString("."))) {
            if (i > 0) {
                return parts.subList(i - 1, parts.size).joinToString(".")
            }
            return null
        }
    }

    return if (parts.size >= 2) parts.takeLast(2).joinToString(".") else null
}

fun isDisposable(email: String): Boolean {
    val domain = email.substringAfter("@")
    val registrable = getRegistrableDomain(domain)
    return registrable != null && disposableEmailDomains.contains(registrable)
}
```

### Swift
contributed by [@1998code](https://github.com/1998code)

```swift
func checkBlockList(email: String, completion: @escaping (Bool) -> Void) {
    let url = URL(string: "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/master/disposable_email_blocklist.conf")!
    let task = URLSession.shared.dataTask(with: url) { data, response, error in
        if let data = data {
            if let string = String(data: data, encoding: .utf8) {
                let lines = string.components(separatedBy: "\n")
                for line in lines {
                    if email.contains(line) {
                        completion(true)
                        return
                    }
                }
            }
        }
        completion(false)
    }
    task.resume()
}
```

### Elixir

```elixir
defmodule MyApp.Email do
  @blocklist File.read!("priv/disposable_email_blocklist.conf")
             |> String.split("\n", trim: true)
             |> MapSet.new()

  def disposable?(email) do
    case String.split(email, "@") do
      [_, domain] ->
        domain_parts = String.split(domain, ".")
        length = length(domain_parts)

        Enum.any?(0..(length - 1), fn i ->
          suffix = Enum.slice(domain_parts, i..-1//1) |> Enum.join(".")
          MapSet.member?(@blocklist, suffix)
        end)

      _ ->
        false
    end
  end
end
```

Alternatively check out Elixir package https://github.com/oshanz/disposable-email.
