"""UNE PHRASE ÉCRITE À CÔTÉ D'UN COMPORTEMENT SE RELIT QUAND IL CHANGE.

Huit constats de la famille ④ du 2e audit, et **une seule maladie** : une
prose, une docstring, une étiquette ou un report qui décrivait un état que
le code n'a plus. Aucun n'aurait fait rougir un test : *une phrase fausse
ne lève pas d'exception — elle envoie seulement son lecteur au mauvais
endroit, et le lecteur ici signe des tarifs.*

CE QUE CHACUN DISAIT, ET CE QUE LA MESURE A TROUVÉ (14/09/2026)

  A5-3     l'étiquette « GLM Poisson (A3) » était écrite EN DUR, alors que
           `glm_de_reference` rend le nom de la famille et que ce nom
           DÉPEND de la cible : Poisson sur la fréquence, **Gamma** sur
           `cout_moyen`, **Tweedie** sur `prime_pure`. L'appelant prenait
           `[1]` (les métriques) et jetait `[0]` (le nom). Sur une cible de
           coût, le document publiait le Gini du Gamma sous le nom du
           Poisson. *La bonne mesure sous le nom du mauvais modèle.*
  A5-4     « 50 époques » en dur, alors que `n_epochs` vaut **200** et que
           `n_epochs_reels` est affiché TROIS LIGNES plus haut dans le même
           texte ; et le conseil « monter à `n_epochs=100` » faisait
           RÉGRESSER celui qui le suivait.
  A5-6     la docstring promettait « la garde rend `0.0` comme A3 et A4 —
           pas `None` ». Relevé des `return` : **quatre `return None`, zéro
           `return 0.0`**, et même chose chez A3 et A4.
  PIPE-2   la docstring annonçait un « taux de REPLI » que le dépôt a
           SUPPRIMÉ, et deux sites le disent (le commentaire d'en dessous
           et `_taxe_du_contrat` : « IL N'Y A PLUS DE REPLI DE TAXE »).
  AGENTS-5 « UTC des deux côtés » — vrai dans ce module, faux pour
           `pipeline_agents`, qui horodate en heure LOCALE.
  CORE-6   un renvoi vers `pipeline_tarifaire.CHARGEMENTS_DEFAUT` quand la
           constante vit à `core/plan_tarifaire.py` ; et un `__all__` qui
           omettait deux publics.
  PIPE-1   la même formule de prime commerciale écrite DEUX fois — et
           **chacun des deux sites portait le commentaire qui l'interdit**,
           sans voir l'autre.
  PERIME-1 un report écrit AU PRÉSENT (« `raisons_plafond` **atteint**
           2 surfaces sur 6 ») alors que le travail a été fait le 12/09 :
           mesure des sites d'appel, **6 surfaces sur 6**.

⚠️⚠️ CE QUE CE SCEAU NE FAIT PAS : relire des phrases. Une sentinelle qui
comparerait du texte à du texte serait la 13e forme du piège d'assiette de
ce dépôt — *le contrôle lit la prose et non le comportement, donc il
passe*. Chaque exigence ci-dessous **dérive du code** ce que la phrase
affirme, et compare les deux.
"""
import ast
import os
import pathlib
import re
import subprocess
import unittest

from core.conformite_reglementaire import glm_de_reference
from core.plan_tarifaire import coefficient_ht

_RACINE = pathlib.Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_A5 = _RACINE / 'direction_non_vie/tarification/a5_deep_learning/agent.py'
_PT = _RACINE / 'direction_non_vie/tarification/pipeline_tarifaire.py'
_EL = _RACINE / 'core/elasticite.py'
_DA = _RACINE / 'core/decision_actuaire.py'
_AR = (_RACINE
       / 'direction_non_vie/tarification/test_archive_fermeture_reportee.py')

#: Un NOMBRE qui quantifie des epoques -- << 50 epoques >>, << epoques=50 >>,
#: << n_epochs=100 >> -- et pas un chiffre qui passait par la (<< A4 >>).
_NOMBRE_D_EPOQUES = re.compile(
    r'\d+\s*(?:é|e)poque|(?:é|e)poques?\s*[:=]\s*\d|n_epochs\s*=\s*\d',
    re.IGNORECASE)

#: ⚠️⚠️ LA SEULE EXEMPTION DE `PH-7`, ET ELLE EST DECLAREE. Les preuves
#: d'audit RECALCULENT la formule pour la verifier : leur faire importer ce
#: qu'elles controlent leur oterait tout sens -- une preuve qui reutilise le
#: code qu'elle verifie ne verifie plus rien. *Ce n'est pas une duplication,
#: c'est le contraire d'une duplication.* Toute AUTRE seconde ecriture reste
#: interdite.
_PREUVES_D_AUDIT = 'direction_non_vie/tarification/audit_2026_08/preuves/'


def _arbre(chemin):
    return ast.parse(chemin.read_text(encoding='utf-8', errors='replace'))


def _production():
    """Les fichiers de production suivis par git -- pas les tests."""
    sortie = subprocess.run(
        ['git', 'ls-files', '*.py'], cwd=str(_RACINE), check=False,
        capture_output=True, text=True, encoding='utf-8',
        errors='replace').stdout
    return [r for r in sortie.split()
            if not pathlib.PurePosixPath(r).name.startswith('test_')]


class TestPhrasesQuiDisentLeVrai(unittest.TestCase):

    # ── PH-1 — A5-3 : l'etiquette DERIVE du nom rendu ────────────────────
    def test_PH1_l_etiquette_du_glm_de_reference_suit_la_cible(self):
        """PAR EXÉCUTION, sur les trois cibles du dépôt plus le cas vide.
        Un contrôle qui lirait le texte de la f-string passerait sur un
        littéral bien choisi."""
        metriques = {'poisson': {'cible': 'nb_sinistres', 'gini': 0.19},
                     'gamma':   {'cible': 'cout_moyen', 'gini': 0.11},
                     'tweedie': {'cible': 'prime_pure', 'gini': 0.19}}
        attendu = {'nb_sinistres': 'Poisson', 'cout_moyen': 'Gamma',
                   'prime_pure': 'Tweedie'}
        for cible, famille in attendu.items():
            nom, _ = glm_de_reference(metriques, cible)
            self.assertIsNotNone(nom, f'aucune reference pour {cible}')
            self.assertEqual(
                nom.capitalize(), famille,
                f"la reference de `{cible}` n'est plus le {famille}")
        self.assertEqual(
            glm_de_reference(metriques, 'cible_inconnue'), (None, None),
            "une cible sans famille doit rendre (None, None), jamais un "
            'nom par defaut')
        #: et le SITE lit bien le nom, au lieu de le jeter
        source = _A5.read_text(encoding='utf-8')
        self.assertNotIn(
            'GLM Poisson (A3) : {', source,
            "l'etiquette du GLM de reference est de nouveau ECRITE EN DUR : "
            'sur une cible de cout ou de prime pure, le document publierait '
            "le Gini du Gamma ou du Tweedie sous le nom du Poisson")

    # ── PH-2 — A5-4 : aucun nombre d'epoques en dur ──────────────────────
    def test_PH2_le_nombre_d_epoques_publie_vient_de_la_mesure(self):
        """Le commentaire actuariel ne porte plus de compte d'époques
        littéral : il lit `n_epochs_reels`."""
        arbre = _arbre(_A5)
        fautifs = []
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.FunctionDef)
                    and noeud.name == '_commenter_actuaire_senior'):
                continue
            for x in ast.walk(noeud):
                if not (isinstance(x, ast.Constant)
                        and isinstance(x.value, str)):
                    continue
                #: ⚠️ LE CHIFFRE DOIT QUANTIFIER LES EPOQUES, pas seulement
                #: cohabiter avec elles. Ma premiere version exigeait
                #: `any(c.isdigit())` et accusait la RECOMMANDATION, qui
                #: contient << A4 >> et << A6 >> a cote du mot << epoques >>.
                #: *Une assiette trop LARGE ne rate pas, elle ACCUSE -- et
                #: ici elle accusait la phrase que ce lot vient d'ecrire.*
                if _NOMBRE_D_EPOQUES.search(x.value):
                    fautifs.append(f'a5:{x.lineno} {x.value.strip()[:60]}')
        self.assertEqual(
            fautifs, [],
            "un nombre d'epoques est de nouveau ECRIT EN DUR dans le "
            f"commentaire signe : {fautifs}")
        self.assertIn(
            'n_epochs_reels', _A5.read_text(encoding='utf-8'),
            'la cle mesuree a disparu : le commentaire ne peut plus la lire')

    # ── PH-3 — A5-6 : la docstring ne promet plus 0.0 ────────────────────
    def test_PH3_aucune_docstring_ne_promet_un_gini_de_zero(self):
        """L'exigence DÉRIVE des `return` : si un jour une garde rend
        vraiment `0.0`, ce contrôle doit s'éteindre tout seul."""
        for rel in ('a3_glm', 'a4_ml', 'a5_deep_learning'):
            chemin = (_RACINE / 'direction_non_vie/tarification' / rel
                      / 'agent.py')
            arbre = _arbre(chemin)
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.FunctionDef)
                        and noeud.name == '_calculer_gini'):
                    continue
                rendus = {ast.unparse(r.value) if r.value else 'None'
                          for r in ast.walk(noeud)
                          if isinstance(r, ast.Return)}
                rend_zero = any(v in ('0.0', '0') for v in rendus)
                doc = ast.get_docstring(noeud) or ''
                promet_zero = '`0.0`' in doc and 'pas `None`' in doc
                self.assertEqual(
                    promet_zero, rend_zero,
                    f"{rel} : la docstring de `_calculer_gini` promet "
                    f"{'0.0' if promet_zero else 'None'} et le code rend "
                    f"{sorted(rendus)}")

    # ── PH-4 — PIPE-2 : aucun repli promis, aucun repli pose ─────────────
    def test_PH4_aucune_prose_ne_promet_un_repli_supprime(self):
        source = _PT.read_text(encoding='utf-8')
        arbre = _arbre(_PT)
        #: le COMPORTEMENT : `_chargements_effectifs` rend `None`, jamais
        #: `CHARGEMENTS_DEFAUT`
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.FunctionDef)
                    and noeud.name == '_chargements_effectifs'):
                continue
            rendus = {ast.unparse(r.value) if r.value else 'None'
                      for r in ast.walk(noeud) if isinstance(r, ast.Return)}
            self.assertNotIn(
                'CHARGEMENTS_DEFAUT', ' '.join(rendus),
                'cette fonction rend de nouveau un repli : la prose et le '
                'commentaire qui disent le contraire deviennent faux')
            doc = ast.get_docstring(noeud) or ''
            self.assertNotIn(
                'taux de REPLI', doc,
                'la docstring promet de nouveau un << taux de REPLI >> que '
                'ni cette fonction ni `_taxe_du_contrat` ne posent')
        self.assertIn(
            "IL N'Y A PLUS DE REPLI DE TAXE", source,
            "le temoin a disparu : ce fichier ne declare plus l'absence de "
            'repli fiscal, donc PH-4 ne mesure plus rien')

    # ── PH-5 — AGENTS-5 : la phrase de portee, DANS LES DEUX SENS ────────
    def test_PH5_la_phrase_sur_UTC_dit_l_etat_reel_des_deux_cotes(self):
        """Deux sens, comme `AG-6` : si l'orchestrateur passe un jour en
        UTC, cette phrase devra le dire aussi — et ce contrôle mordra."""
        source_pt = _PT.read_text(encoding='utf-8')
        chemin_pa = (_RACINE
                     / 'direction_non_vie/tarification/pipeline_agents.py')
        locaux = [n.lineno for n in ast.walk(_arbre(chemin_pa))
                  if isinstance(n, ast.Call)
                  and 'astimezone' in ast.unparse(n)[:80]]
        if locaux:
            self.assertNotIn(
                'UTC des deux cotes', source_pt,
                f"`pipeline_agents` horodate en heure LOCALE (l.{locaux}) : "
                'la phrase << UTC des deux cotes >> est FAUSSE')
        else:
            self.assertIn(
                'UTC des deux cotes', source_pt,
                "`pipeline_agents` est passe en UTC : la phrase de portee "
                'doit le dire, elle limite desormais a tort')

    # ── PH-6 — CORE-6 : le renvoi et le `__all__` ────────────────────────
    def test_PH6_le_renvoi_designe_le_module_qui_definit_la_constante(self):
        porteurs = []
        for rel in _production():
            try:
                arbre = _arbre(_RACINE / rel)
            except (OSError, SyntaxError):
                continue
            for noeud in arbre.body:
                cibles = []
                if isinstance(noeud, ast.Assign):
                    cibles = [t.id for t in noeud.targets
                              if isinstance(t, ast.Name)]
                elif (isinstance(noeud, ast.AnnAssign)
                        and isinstance(noeud.target, ast.Name)):
                    cibles = [noeud.target.id]
                if 'CHARGEMENTS_DEFAUT' in cibles:
                    porteurs.append(rel)
        self.assertEqual(
            len(porteurs), 1,
            f'`CHARGEMENTS_DEFAUT` est defini {len(porteurs)} fois : '
            f'{porteurs}. Un renvoi ne peut plus designer une source unique')
        module = porteurs[0][:-3].replace('/', '.')
        source_el = _EL.read_text(encoding='utf-8')
        self.assertIn(
            f'`{module}.CHARGEMENTS_DEFAUT`', source_el,
            f'la prose ne renvoie pas au module qui DEFINIT la constante '
            f'({module})')

    def test_PH6b_le_all_de_decision_actuaire_expose_tous_ses_publics(self):
        arbre = _arbre(_DA)
        expose = set()
        for noeud in arbre.body:
            if isinstance(noeud, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == '__all__'
                    for t in noeud.targets):
                expose = {c.value for c in ast.walk(noeud.value)
                          if isinstance(c, ast.Constant)
                          and isinstance(c.value, str)}
        publics = {x.name for x in arbre.body
                   if isinstance(x, (ast.FunctionDef, ast.ClassDef))
                   and not x.name.startswith('_')}
        publics |= {t.id for x in arbre.body if isinstance(x, ast.Assign)
                    for t in x.targets if isinstance(t, ast.Name)
                    and t.id.isupper() and t.id != '__all__'}
        self.assertTrue(publics, 'temoin mort : aucun public recense')
        self.assertEqual(
            sorted(publics - expose), [],
            f'`__all__` omet des publics : {sorted(publics - expose)}')

    # ── PH-7 — PIPE-1 : UNE seule ecriture de la formule ─────────────────
    def test_PH7_la_formule_de_prime_commerciale_n_est_ecrite_qu_une_fois(self):
        """Relevé par AST sur tout le code de production : on cherche la
        FORME de l'expression, pas son texte — un espace de plus ne doit pas
        la cacher."""
        sites = []
        for rel in _production():
            if rel.startswith(_PREUVES_D_AUDIT):
                continue          # exemption declaree en tete de fichier
            try:
                arbre = _arbre(_RACINE / rel)
            except (OSError, SyntaxError):
                continue
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.BinOp):
                    continue
                texte = ast.unparse(noeud).replace(' ', '')
                if ("1-" in texte and "'commission'" in texte
                        and "'frais'" in texte and "'marge'" in texte):
                    sites.append(f'{rel}:{noeud.lineno}')
        #: les BinOp s'emboitent : on compte les FICHIERS, pas les noeuds
        fichiers = sorted({s.rsplit(':', 1)[0] for s in sites})
        self.assertEqual(
            len(fichiers), 1,
            f'la formule de prime commerciale est ecrite dans '
            f'{len(fichiers)} fichier(s) : {fichiers}. *Deux redactions de '
            f'la meme formule finissent par en dire deux choses* -- et les '
            f'deux anciens sites portaient chacun cette phrase.')

    def test_PH7b_la_formule_deplacee_rend_exactement_le_meme_nombre(self):
        """La contre-épreuve du déménagement : bit à bit, sur 100 triplets."""
        ecarts = []
        for frais in (0.0, 0.05, 0.15, 0.4, 1.2):
            for marge in (0.0, 0.03, 0.25, 0.9):
                for commission in (0.0, 0.10, 0.35, 0.75, 0.99):
                    ancien = ((1 + frais) * (1 + marge) / (1 - commission))
                    neuf = coefficient_ht({'frais': frais, 'marge': marge,
                                           'commission': commission})
                    if neuf != ancien:
                        ecarts.append((frais, marge, commission, neuf, ancien))
        self.assertEqual(
            ecarts, [],
            f'la formule deplacee ne rend plus le meme nombre : {ecarts[:4]}')

    # ── PH-8 — PERIME-1 : un report ne survit pas a sa raison ────────────
    def test_PH8_le_report_ne_dit_plus_qu_il_reste_a_faire(self):
        """La portée DÉCLARÉE dans le registre est confrontée à la portée
        MESURÉE par AST. Un report qui annonce un travail déjà fait envoie
        le prochain lecteur le refaire ou l'éviter pour rien."""
        lecteurs = set()
        for rel in _production():
            try:
                arbre = _arbre(_RACINE / rel)
            except (OSError, SyntaxError):
                continue
            for noeud in ast.walk(arbre):
                appel = ''
                if isinstance(noeud, ast.Call):
                    appel = (noeud.func.attr
                             if isinstance(noeud.func, ast.Attribute)
                             else getattr(noeud.func, 'id', ''))
                if appel in ('synthese_raisons_plafond', 'raisons_plafond'):
                    lecteurs.add(rel)
        self.assertGreaterEqual(
            len(lecteurs), 3,
            f'`raisons_plafond` n atteint plus que {sorted(lecteurs)} : le '
            f'report redevient vrai, et ce controle doit etre rouvert')
        texte = _AR.read_text(encoding='utf-8')
        self.assertNotIn(
            '`raisons_plafond` atteint 2 surfaces sur 6', texte,
            'le registre annonce de nouveau AU PRESENT un travail qui a ete '
            'fait le 12/09/2026')


if __name__ == '__main__':
    unittest.main(verbosity=2)
