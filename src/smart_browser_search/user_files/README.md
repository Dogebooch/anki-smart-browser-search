# user_files

This folder is created/owned by the **Smart Browser Search** add-on and is the
only folder Anki preserves across add-on updates.

The add-on stores its semantic index here (`index.db`) and an optional debug log
(`smart_search.log`). **Nothing here touches your Anki collection** — `index.db`
is a completely separate SQLite database. You can safely delete `index.db` to
force a full re-index; the add-on will rebuild it on demand.
