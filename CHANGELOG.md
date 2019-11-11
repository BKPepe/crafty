# Changelog
All notable changes to this project will be documented in this file.

## [v2.0.beta]
This version of Crafty focuses on Schedules, and more customization of 
Crafty via configuration options.  

### Additions
- Addition of schedules

### Changes
- moved scheduled logs to own file
- removed old Alpha 1 documentation - replaced with page that links to craftycontrol.com
- fixed windows path issues / errors.


## [v2.0.alpha]
This version of Crafty is a complete rebuild of Crafty from the ground up.
Crafty is now a web based platform and thus is a different product than
Crafty 1.0, hence the 2.0 name.

- [Tornado](https://www.tornadoweb.org/en/stable/) webserver used as a backend for the web side.
- [Argon2](https://pypi.org/project/argon2-cffi/) used for password hashing
- [SQLite DB](https://www.sqlite.org/index.html) used for settings.
- [Adminlte](https://adminlte.io/themes/AdminLTE/index2.html) used for web templating
- [Font Awesome 4](https://fontawesome.com/) used for Buttons 
