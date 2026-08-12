# -*- coding: utf-8 -*-
"""Mesure IFRS 17 — la méthode d'affectation des primes (§55-59).

⚠️ FRONTIÈRE AVEC LE SOCLE, TENUE DANS LES DEUX SENS. Le socle
(`normes/ifrs17/socle/`) répond à « quels groupes existent » et ne porte
AUCUN montant — un test l'interdit. Ce paquet-ci répond à « combien
valent-ils ». Il ne prend donc pas de `Groupe` en entrée : il prend des
montants nommés, et l'appariement des deux relève de l'appelant.

⚠️ ET IL NE DÉCIDE PAS DE L'ÉLIGIBILITÉ. §53 s'apprécie à la création du
groupe et le socle le scelle ; mesurer en PAA un groupe qui n'y a pas droit
serait une faute que ce paquet ne peut pas rattraper. Il exige donc que
l'éligibilité lui soit DÉCLARÉE, et refuse à défaut.
"""
