List of disposable email domains
========================

This repo contains a [list of disposable and temporary email address domains](disposable_email_blacklist.conf) often used to register dummy users in order to spam/abuse some services. 

Originally collected to filter new user registration at https://usegalaxy.org and later merged with other lists found online. I cannot guarantee all of these can still be considered disposable but they probably were at one point in time.

Whitelist
=========
The file [whitelist.conf](whitelist.conf) gathers email domains that are often identified as disposable but in fact are not.

Example Usage
=============
Python
```Python
blacklist = ('disposable_email_blacklist.conf')
blacklist_content = [line.rstrip() for line in blacklist.readlines()]
if email.split('@')[1] in blacklist_content:
    message = "Please enter your permanent email address."
    return (False, message)
else:
    return True
```
PHP contributed by @txt3rob and @deguif
```php
function is_temp_mail($mail) {
    $mail_domains_ko = file('disposable_email_blacklist.conf', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

    //Need to ensure the mail contains an @ to avoid undefined offset
    return in_array(explode('@', $mail)[1], $mail_domains_ko);
}
```

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

Use 

`$ cat disposable_email_blacklist.conf your_file | tr '[:upper:]' '[:lower:]' | sort -f | uniq -i  > new_file.conf`

`$ comm -23 new_file.conf whitelist.conf > disposable_email_blacklist.conf`

to add contents of another file in the same format (domains on new line without @). It also converts uppercase to lowercase, sorts, removes duplicates and removes whitelisted domains.
