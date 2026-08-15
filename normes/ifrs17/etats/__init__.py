# -*- coding: utf-8 -*-
"""Le paquet qui ASSEMBLE — et que rien ne doit importer.

⚠️⚠️ TROISIÈME ZONE, ET LA MESURE L'A EXIGÉE. « Le socle est le fondement,
la mesure est au-dessus » est FAUX : mesuré sur l'AST, `socle → mesure`
compte 2 arcs de production (`cloture` et `errata_donnees` vers
`mesure.declaration`) et `mesure → socle` en compte 1
(`reassurance_61_62` vers `socle.errata_donnees`). Les deux paquets sont
déjà mutuellement dépendants.

⚠️ Poser l'orchestrateur dans l'un des deux APPROFONDIRAIT ce cycle. Ici, le
graphe redevient acyclique : `etats → {socle, mesure} → core`.

⚠️⚠️ ET C'EST LE SEUL MODULE QUI DOIT TENIR UN `Groupe`, UN `Magasin`, UN
`Bilan` ET LE `PERIMETRE` ENSEMBLE. Chaque frontière du chantier interdit
précisément cela — `test_aucune_dependance_au_socle` refuse que la mesure
prenne un `Groupe`. L'orchestrateur est l'EXCEPTION, et une exception doit
vivre là où on peut la nommer et la borner.

⚠️ LE VERROU EST DANS `test_assemblage.py` : ce paquet peut tout importer,
RIEN ne peut l'importer. Sans lui, le cycle se reformerait par le bas.
"""
