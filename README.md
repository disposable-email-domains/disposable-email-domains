disposable-email-domains
========================

This repo contains a list of disposable and temporary email address domains often used to register dummy users in order to spam/abuse some services. Also useful for filtering your email list to increase open rates (sending email to these domains likely will not be opened).

I originally collected them to filter allowed domains for new user registration at usegalaxy.org and later merged them with other lists I have found online. I cannot guarantee all of these can still be considered but I did go through all of them at one point.

Feel free to create PR with more or request removing of your domain (with reasons).

Use `cat disposable_email_blacklist.conf your_file | sort | uniq > disposable_email_blacklist.conf` to add contents of another file in the same format (domains on new line without @).
