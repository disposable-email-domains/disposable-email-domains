disposable-email-domains
========================

This repo contains list of disposable domains often used to register dummy users in order to spam/abuse some services. I collected them to filter allowed domains for new user registration at usegalaxy.org

Feel free to create PR with more or request removing of your domain (with reasons).

Use `cat disposable_email_blacklist.conf your_file | sort | uniq > disposable_email_blacklist.conf` to add contents of another file in the same format (domains on new line without @).
