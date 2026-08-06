# -*- coding: utf-8 -*-
"""Normes comptables et prudentielles — TRANSVERSALES AUX DIRECTIONS MÉTIER.

⚠️ POURQUOI CE PAQUET EXISTE À LA RACINE. IFRS 17 n'est pas une technique
actuarielle propre au non-vie : c'est une norme comptable. Un assureur qui
exerce en non-vie ET en santé publie UN SEUL jeu d'états financiers, pas
deux. Ranger la norme dans une direction métier la découperait selon un axe
qui n'est pas le sien, et obligerait à reconstruire son socle une fois par
direction.

Les directions métier ALIMENTENT ce paquet ; c'est lui qui produit les états.

⚠️ CE PAQUET A SA PROPRE GATE. `direction_non_vie` n'en fait pas partie :
    py -m unittest discover -s direction_non_vie -t .
    py -m unittest discover -s normes -t .
Les deux commandes doivent être vertes. Voir `ifrs17/socle/contrat.py`.
"""
