"""
==============================================================================
  D'OU VIENT LE PRIX, ET CE QUE LE CLASSEMENT RECOMMANDE
==============================================================================

⚠️⚠️ UNE OMISSION, PAS UN MENSONGE -- et c'est la mesure qui l'a etabli.
Sonde du 09/09/2026 sur le document reellement produit (`a6 HTML`, 235 ko) :

  R1  le rapport NOMME un modele retenu -- << NE PAS deployer GLM_POISSON en
      l'etat... soumettre le modele a la validation de l'actuaire >> ;
  R2  le bloc PRIX ne dit RIEN de son origine : ni << GLM >>, ni un nom de
      modele ;
  R3  AUCUNE phrase ne relie les deux : `GLM_POISSON` n'apparait jamais a
      cote d'un prix, d'une prime ou d'un tarif.

*Le document ne mentait pas : il se taisait.* Un lecteur voit << modele de
production >> dans une section et un prix dans une autre, et les relie.
Aujourd'hui il a raison PAR COINCIDENCE -- les deux sont un GLM Poisson.

⚠️⚠️ ET LA COINCIDENCE N'EST PAS GARANTIE. Le classement et le tarif ne se
croisent nulle part : `pipeline_complet` ne lit jamais `result_a6`. Or la
marge du vainqueur relevee sur un run reel vaut 0,0357 (GLM_POISSON 0,6602
contre DL_CANN 0,6245), pendant qu'un changement de decoupe fait varier le
Gini d'un facteur allant jusqu'a 3,8, pondere 0,40 dans la grille.

⚠️ CE QUI N'A PAS ETE FAIT, ET C'EST DELIBERE : faire alimenter le prix par le
modele classe. Ce serait une refonte du produit, pas une correction de defaut,
et elle deplacerait des euros. *On dit ce qui est.*

⚠️ ET L'ALERTE SE TAIT QUAND LES DEUX COINCIDENT. Une alerte permanente ne
signalerait plus rien le jour ou elle compterait.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.origine_du_prix import MODELE_DU_TARIF, phrase_origine_du_prix

_RAPPORT = ('direction_non_vie/tarification/services/'
            'rapport_modeles_tarif.py')


class TestCeQuiAProduitLePrix(unittest.TestCase):

    def test_OP1_le_prix_NOMME_ce_qui_l_a_produit(self):
        """⚠️⚠️ LE DEFAUT MESURE : le bloc prix ne disait ni << GLM >>, ni un
        nom de modele, ni une famille de cout."""
        phrase = phrase_origine_du_prix('gamma')
        self.assertIn('FREQUENCE', phrase.upper())
        self.assertIn('Poisson', phrase)
        self.assertIn('COUT', phrase.upper())
        self.assertIn('gamma', phrase)
        self.assertIn('equilibre', phrase)
        print("    OP-1 le prix nomme sa frequence, son cout et son calage")

    def test_OP2_une_famille_NON_DECLAREE_se_dit_elle_ne_se_devine_pas(self):
        """⚠️ La loi de cout vient du PLAN. `None` se dit, il ne se remplace
        pas par un defaut -- meme doctrine que les chargements et les taux."""
        for absente in (None, '', '   '):
            self.assertIn('non declaree', phrase_origine_du_prix(absente))
        print("    OP-2 famille non declaree : dite, jamais devinee")

    def test_OP3_LE_SCEAU_une_DIVERGENCE_est_signalee_et_nommee(self):
        """⚠️⚠️ LE CAS QUI COMPTE. Le classement recommande un modele que le
        tarif n'utilise pas : le lecteur doit l'apprendre du document, pas le
        deduire de deux sections eloignees."""
        phrase = phrase_origine_du_prix('gamma',
                                        modele_recommande='ML_CATBOOST')
        self.assertIn("N'EST PAS CELUI QUI A PRODUIT CE PRIX", phrase)
        self.assertIn('ML_CATBOOST', phrase)
        self.assertIn(MODELE_DU_TARIF, phrase)
        self.assertIn('ne determine pas le prix publie', phrase)
        print("    OP-3 SCEAU : divergence signalee, les DEUX modeles nommes")

    def test_OP4_LE_MIROIR_aucune_alerte_quand_les_deux_COINCIDENT(self):
        """⚠️⚠️ SANS CE SENS, UNE ALERTE PERMANENTE SATISFERAIT OP-3 -- et elle
        ne signalerait plus rien le jour ou elle compterait. C'est la doctrine
        du refus d'anti-selection et de la bande de niveau."""
        for meme in (MODELE_DU_TARIF, MODELE_DU_TARIF.lower(), None, '', '  '):
            self.assertNotIn("N'EST PAS CELUI QUI A PRODUIT",
                             phrase_origine_du_prix('gamma', meme),
                             f"alerte declenchee a tort pour {meme!r}")
        print("    OP-4 miroir : aucune alerte quand les deux coincident")

    def test_OP5_le_socle_ne_remonte_PAS_vers_une_direction(self):
        socle = (pathlib.Path(_RACINE) / 'core'
                 / 'origine_du_prix.py').read_text(encoding='utf-8')
        remontees = [n.module for n in ast.walk(ast.parse(socle))
                     if isinstance(n, ast.ImportFrom) and n.module
                     and n.module.startswith('direction_')]
        self.assertEqual(remontees, [], f"le socle importe : {remontees}")
        print("    OP-5 le socle n'importe aucune direction")


class TestLeBranchementDeLOrigine(unittest.TestCase):

    def test_OP6_LE_SCEAU_le_bloc_prix_PUBLIE_l_origine_dans_les_deux_formats(
            self):
        """⚠️⚠️ LA SIXIEME ASYMETRIE QUE CE DEPOT AURAIT PAYEE. Le mapping,
        l'elasticite, la qualite, les reserves d'A6, la comparaison de prix et
        les conditions de mesure avaient chacun atteint UN SEUL format."""
        chemin = pathlib.Path(_RACINE) / _RAPPORT
        texte = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(texte)
        html = mots = False
        for f in ast.walk(arbre):
            if not isinstance(f, ast.FunctionDef):
                continue
            src = ast.get_source_segment(texte, f) or ''
            if f.name == '_bloc_tarif_html':
                html = "'origine'" in src or '"origine"' in src
            if f.name == 'export_word':
                mots = "'origine'" in src or '"origine"' in src
        self.assertTrue(html, "le bloc HTML du prix ne publie pas l'origine")
        self.assertTrue(mots, "le Word ne publie pas l'origine")
        print("    OP-6 SCEAU : les deux formats publient l'origine du prix")

    def test_OP7_LE_SCEAU_les_DEUX_appelants_fournissent_le_modele_recommande(
            self):
        """⚠️⚠️ SANS CET ARGUMENT, L'ALERTE NE PEUT JAMAIS SE DECLENCHER : un
        garde-fou dont l'assiette est vide. Releve PAR AST sur les appels
        REELS, pas sur la signature -- une signature qui accepte un argument
        ne prouve pas qu'un appelant le remplisse."""
        chemin = pathlib.Path(_RACINE) / _RAPPORT
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        # ⚠️⚠️ ON SUIT LA VALEUR, ON NE FILTRE PAS SUR LA FORME DE L'APPEL.
        # Un appelant passe une variable assignee deux lignes plus haut : un
        # controle qui ne lirait que l'expression de l'appel le declarerait
        # fautif a tort. *L'assiette d'un controle est ce qu'il surveille, ni
        # plus ni moins* -- trop LARGE, il laisse passer (defaut `CM-4`) ;
        # trop ETROITE, il accuse a tort (ce controle, premier jet).
        assignations = {
            cible.id: ast.unparse(n.value)
            for n in ast.walk(arbre) if isinstance(n, ast.Assign)
            for cible in n.targets if isinstance(cible, ast.Name)}
        appels = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', None) == 'tarif_publie']
        self.assertTrue(appels, "plus aucun appel a `tarif_publie`")
        for appel in appels:
            fournis = list(appel.args) + [k.value for k in appel.keywords]
            self.assertGreaterEqual(
                len(fournis), 3,
                f"un appel a `tarif_publie` ne fournit que {len(fournis)} "
                f"argument(s) : le modele recommande manque, et l'alerte de "
                f"divergence ne pourra jamais se declencher")
            troisieme = fournis[2]
            source = (assignations.get(troisieme.id, troisieme.id)
                      if isinstance(troisieme, ast.Name)
                      else ast.unparse(troisieme))
            self.assertIn('modele_production', source,
                          f"l'appel ne lit pas le modele retenu par A6 : "
                          f"l'argument vaut `{source[:80]}`")
        print(f"    OP-7 SCEAU : les {len(appels)} appels fournissent le "
              f"modele recommande")

    def test_OP8_le_tarif_ne_lit_JAMAIS_le_classement_releve_par_AST(self):
        """⚠️⚠️ LA PREMISSE DE TOUT CE LOT, ET ELLE SE VERIFIE. Si un jour le
        tarif lisait `result_a6`, l'alerte deviendrait fausse : elle dirait
        que les deux mecanismes ne se croisent pas alors qu'ils se
        croiseraient. *Une phrase publiee doit rester vraie, ou rougir.*"""
        pipeline = (pathlib.Path(_RACINE) / 'direction_non_vie'
                    / 'tarification' / 'pipeline_tarifaire.py').read_text(
                        encoding='utf-8')
        arbre = ast.parse(pipeline)
        noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        noms |= {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
        for interdit in ('result_a6', 'modele_production', 'classement'):
            self.assertNotIn(
                interdit, noms,
                f"`pipeline_tarifaire` lit '{interdit}' : le prix depend "
                f"desormais du classement, et la phrase publiee est FAUSSE")
        print("    OP-8 le tarif ne lit ni result_a6, ni le classement")


if __name__ == '__main__':
    unittest.main(verbosity=2)
