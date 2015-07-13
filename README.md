List of disposable email domains
========================

This repo contains a list of disposable and temporary email address domains often used to register dummy users in order to spam/abuse some services. It is also useful for filtering your email list to increase open rates (sending email to these domains is probably useless).

Originally collected to filter new user registration at https://usegalaxy.org and later merged with other lists found online. I cannot guarantee all of these can still be considered disposable but they probably were at one point in time.

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
PHP contributed by @txt3rob
```php
function is_temp_mail($mail) {
    $list = file_get_contents ('disposable_email_blacklist.conf');
    $mail_domains_ko = explode("\n", $list);
    foreach($mail_domains_ko as $ko_mail) {
        list(,$mail_domain) = explode('@',$mail);
        if(strcasecmp($mail_domain, $ko_mail) == 0){
            return true;
        }
    }
    return false;
}
```

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

Use 

`cat disposable_email_blacklist.conf your_file | sort -f | uniq -i  > new_file`

to add contents of another file in the same format (domains on new line without @).
