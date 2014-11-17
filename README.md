List of disposable email domains
========================

This repo contains a list of disposable and temporary email address domains often used to register dummy users in order to spam/abuse some services. It is also useful for filtering your email list to increase open rates (sending email to these domains likely will not be opened).

I originally collected some of them to filter allowed domains for new user registration at usegalaxy.org and later merged them with other lists I have found online. I cannot guarantee all of these can still be considered disposable but they probably were at one point in time.

Contributing
============
Feel free to create PR with additions or request removal of some domain (with reasons).

Use 

`cat disposable_email_blacklist.conf your_file | sort -f | uniq -i  > new_file`

to add contents of another file in the same format (domains on new line without @).
