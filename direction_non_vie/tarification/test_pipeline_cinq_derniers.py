"""Controles positifs — `pipeline` : C2, C3, C6, C7, C9, les cinq derniers.

CE QUE LA MESURE A TROUVE, ET CE QU'ELLE A REFUTE
──────────────────────────────────────────────────

⚠️⚠️ `C2` EST REFUTE SUR SA FORME, ET CE QUI RESTE EST PIRE. Il disait que le
repli << aucun cout observe : cout moyen constant (degenere mais defini) >>
n'etait JAMAIS atteint, mesure sur un portefeuille SANS aucun sinistre. Ce
cas-la meurt bien vingt lignes plus tot -- mais sur le GLM de FREQUENCE, pas
faute d'atteindre le repli.

**La branche EST atteinte par l'AUTRE cas** : des sinistres COMPTES, aucun cout
POSITIF. Et mesure du 01/09 : **elle meurt elle-meme**, l.570, parce qu'elle
ajustait un GLM Gamma sur **UNE observation** et ~24 parametres.

> *<< Degenere mais defini >> n'etait ni l'un ni l'autre. Le constat visait
> juste et se trompait de porte.*

⚠️⚠️ ET LES DEUX MORTS PORTAIENT LE MEME MESSAGE, CELUI DE `pipeline/C8` :

```
  ValueError: The first guess on the deviance function returned a nan.
              This could be a boundary problem and should be reported.
```

*L'actuaire etait invite a signaler un bug a `statsmodels` la ou son
portefeuille n'avait simplement aucun sinistre.* Les deux impossibilites sont
desormais NOMMEES avant le solveur. ⚠️ **Aucun euro : il n'y avait pas de prix,
il n'y en a toujours pas -- mais on dit pourquoi.**

═══ LES QUATRE AUTRES — DES PHRASES QUI AFFIRMAIENT AU-DELA ═══

| constat | ce qu'elle disait | ce que la mesure montre |
|---|---|---|
| `C3` | << UNE SEULE definition >> du Gini | vrai DANS CE MODULE, faux dans le depot : **8 fonctions calculent** |
| `C6` | << relativites exportables >> | elle ne portait que la FREQUENCE -- la moitie du tarif |
| `C7` | << l'un reproduise l'autre a 1e-6 >> | `tarifer()` ARRONDIT au centime : la precision n'est pas observable |
| `C9` | deux horodatages du meme calcul | l'un en UTC, l'autre en heure LOCALE |

⚠️ `C6` EST LE SEUL QUI TOUCHE UN COMPORTEMENT : la grille porte desormais
`relativite_cout` et `relativite_prime_pure`, parce que la prime pure est
**frequence x cout**. *L'assureur etait invite a mettre dans son SI une grille
dont il manquait un facteur sur deux.* **Aucun euro** : `grille()` n'entre dans
aucun calcul de prime, elle EXPOSE ce que les deux GLM portent deja.
"""

from __future__ import annotations

import ast
import inspect
import logging
import pathlib
import unittest
import warnings

from direction_non_vie.tarification.pipeline_tarifaire import (
    CalculImpossibleBloquant,
    TarifNonVie,
    gini_lorenz,
    pipeline_complet,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_CONTRAT = {
    'age': 40, 'bonus_malus': 0.9, 'anciennete_permis': 20,
    'puissance_fiscale': 6, 'age_vehicule': 5, 'valeur_venale': 12000,
    'garantie': 'TousRisques', 'carburant': 'Diesel', 'csp': 'Cadre',
    'usage': 'Prive', 'antecedents_sinistres_n1': 0,
    'kilometrage_annuel': 12000, 'milieu_geographique': 'Urbain',
}


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _tarif(df=None):
    return _sans_bruit(
        pipeline_complet,
        _portefeuille_auto(800, seed=3) if df is None else df,
        _PLAN_AUTO, qualite_validee_par='Selasse Sekle')


class TestC2LesDeuxImpossibilites(unittest.TestCase):
    """⚠️⚠️ LE REPLI << DEGENERE MAIS DEFINI >> N'ETAIT NI L'UN NI L'AUTRE."""

    def test_LE_TEST_QUI_FERME_aucun_sinistre_est_REFUSE_et_NOMME(self):
        """⚠️ Il mourait sur `deviance function returned a nan ... should be
        reported`. *Un message qui accuse la bibliotheque et non le fichier.*"""
        df = _portefeuille_auto(600, seed=3)
        df['nb_sinistres'] = 0.0
        df['cout_total_sinistres'] = 0.0
        with self.assertRaises(CalculImpossibleBloquant) as leve:
            _tarif(df)
        msg = str(leve.exception)
        self.assertIn('NULLE sur tout le portefeuille', msg)
        self.assertIn('nb_sinistres', msg)
        self.assertIn("absence d'experience", msg)
        print(f"    PC-1 aucun sinistre -> refus NOMME : {msg[:64]}...")

    def test_des_sinistres_SANS_cout_atteignent_le_repli_et_sont_REFUSES(self):
        """⚠️⚠️ C'EST LE CAS QUE LE CONSTAT AVAIT MANQUE. Il concluait
        << branche jamais atteinte >> sur un portefeuille sans sinistre ; la
        branche est atteinte par celui-ci, et elle mourait dedans."""
        df = _portefeuille_auto(600, seed=3)
        df['cout_total_sinistres'] = 0.0
        self.assertGreater(int((df['nb_sinistres'] > 0).sum()), 0,
                           'sans sinistre compte, ce test mesurerait le cas '
                           'precedent')
        with self.assertRaises(CalculImpossibleBloquant) as leve:
            _tarif(df)
        msg = str(leve.exception)
        self.assertIn('sinistre(s) sont COMPTES', msg)
        self.assertIn('AUCUN cout strictement positif', msg)
        self.assertIn('incoherence_sin_sans_cout', msg)
        print(f"    PC-2 sinistres sans cout -> refus NOMME : {msg[:60]}...")

    def test_second_sens_un_portefeuille_NORMAL_tarife(self):
        """⚠️ Un refus qui tomberait toujours ne protegerait de rien."""
        t = _tarif()
        self.assertGreater(t.coefficient_equilibre, 0)
        print(f"    PC-3 portefeuille normal : k={t.coefficient_equilibre:.5f}")


class TestC3LaPortee(unittest.TestCase):

    def test_la_phrase_LIMITE_sa_portee_au_lieu_de_l_affirmer(self):
        """⚠️⚠️ *Une phrase qui LIMITE est sure ; une phrase qui AFFIRME
        au-dela de ce qu'elle tient est une dette.*"""
        doc = inspect.getdoc(gini_lorenz) or ''
        self.assertNotIn('UNE SEULE définition, utilisée', doc)
        # ⚠️ ON CHERCHE UNE PHRASE QUI NE SE COUPE PAS. Ma premiere version
        # cherchait « DANS CE MODULE » : le texte l'ecrit a cheval sur un
        # retour a la ligne. *Un document destine a etre verifie porte ses
        # phrases telles qu'on les cherchera* — et un controle ne cherche
        # que ce qui ne se coupe pas.
        self.assertIn('dans ce module', doc)
        self.assertIn("pas l'unicité dans le dépôt", doc)
        self.assertIn('SUR-compte', doc)
        print("    PC-4 la portee est LIMITEE au module, et la methode du "
              "comptage est publiee avec son sens d'erreur")

    def test_le_compte_annonce_est_CELUI_QUE_LA_MESURE_DONNE(self):
        """⚠️⚠️ ON RE-DERIVE, on ne croit pas la phrase. Meme critere que celui
        qu'elle publie : un corps qui emploie `cumsum`, `trapz` ou Lorenz."""
        calculent = []
        for chemin in sorted(_RACINE.rglob('*.py')):
            s = chemin.as_posix()
            if ('.venv' in s or '/audit_2026_08/' in s
                    or chemin.name.startswith('test_')):
                continue
            source = chemin.read_text(encoding='utf-8', errors='replace')
            try:
                arbre = ast.parse(source)
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(arbre):
                if (isinstance(n, ast.FunctionDef)
                        and 'gini' in n.name.lower()):
                    corps = ast.get_source_segment(source, n) or ''
                    if ('cumsum' in corps or 'trapz' in corps
                            or 'lorenz' in corps.lower()):
                        # ⚠️ LA CLE EST LE CHEMIN COMPLET, pas le nom de
                        # fichier : `a3`, `a4` et `a5` ont TOUS un
                        # `agent.py::_calculer_gini`. Ma premiere version
                        # annoncait « 6 distinctes » pour 8 trouvees —
                        # *une cle qui COLLISIONNE sous-compte en silence.*
                        calculent.append(f'{s}::{n.name}')
        self.assertEqual(
            len(calculent), 8,
            f"la docstring annonce 8 fonctions qui calculent un Gini, la "
            f"mesure en trouve {len(calculent)} : {sorted(calculent)}")
        self.assertIn('**8 calculent', inspect.getdoc(gini_lorenz) or '')
        print(f"    PC-5 8 fonctions calculent un Gini, comme annonce : "
              f"{len(set(calculent))} distinctes")


class TestC6LaGrillePorteToutLeTarif(unittest.TestCase):

    def test_LE_TEST_QUI_FERME_les_deux_moities_du_tarif_sont_exportees(self):
        """⚠️⚠️ La prime pure est **frequence x cout**. La grille n'en portait
        qu'une : *l'assureur mettait dans son SI un facteur sur deux.*"""
        g = _tarif().grille('bonus_malus')
        self.assertEqual(list(g.columns),
                         ['colonne', 'relativite_frequence',
                          'relativite_cout', 'relativite_prime_pure'])
        self.assertFalse(g.empty, 'la grille est vide : rien n est prouve')
        ligne = g.iloc[0]
        # ⚠️ La troisieme colonne EST le produit des deux premieres : c'est ce
        # qui fait d'elle le tarif, et non deux nombres cote a cote.
        self.assertAlmostEqual(
            float(ligne['relativite_prime_pure']),
            float(ligne['relativite_frequence'])
            * float(ligne['relativite_cout']), places=3)
        print(f"    PC-6 grille : freq={ligne['relativite_frequence']} x "
              f"cout={ligne['relativite_cout']} = "
              f"{ligne['relativite_prime_pure']}")

    def test_second_sens_une_variable_INCONNUE_rend_une_grille_VIDE(self):
        """⚠️ Sans ce sens, une grille qui rendrait toujours des lignes
        passerait le controle precedent sans rien garantir."""
        g = _tarif().grille('variable_qui_n_existe_pas')
        self.assertTrue(g.empty)
        self.assertEqual(list(g.columns),
                         ['colonne', 'relativite_frequence',
                          'relativite_cout', 'relativite_prime_pure'])
        print("    PC-7 variable inconnue : grille vide, colonnes stables")


class TestC7EtC9(unittest.TestCase):

    def test_C7_la_docstring_ne_promet_plus_une_precision_INOBSERVABLE(self):
        """⚠️ `tarifer()` arrondit au centime : 1e-6 n'y est pas verifiable.
        *L'oracle etait juste ; c'est la phrase qui promettait au-dela.*"""
        doc = inspect.getdoc(TarifNonVie.predire_portefeuille) or ''
        self.assertNotIn("pour que l'un reproduise l'autre à 1e-6", doc)
        self.assertIn('arrondit', doc)
        self.assertIn('0,0036', doc)
        print("    PC-8 la promesse porte sur le CHEMIN, pas sur la sortie "
              "arrondie")

    def test_C9_les_deux_horodatages_portent_LE_MEME_fuseau(self):
        """⚠️⚠️ *Un horodatage sans fuseau n'est pas un horodatage, c'est une
        supposition sur la machine qui l'a ecrit.*"""
        t = _tarif()
        signe = t.tarifer(_CONTRAT)['date_calcul']
        qualite = t.rapport_qualite.horodatage
        for etiquette, valeur in (('date_calcul', signe),
                                  ('rapport_qualite', qualite)):
            with self.subTest(quoi=etiquette):
                self.assertTrue(valeur.endswith('+00:00'),
                                f"{etiquette} n'est pas en UTC : {valeur}")
        print(f"    PC-9 les deux traces en UTC : {signe[-6:]} et "
              f"{qualite[-6:]}")


if __name__ == '__main__':
    unittest.main()
