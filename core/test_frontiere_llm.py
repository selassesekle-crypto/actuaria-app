# -*- coding: utf-8 -*-
"""Tests C1 — la frontière unique, et le verrou qui la rend vraie.

⚠️ GATE : `py -m unittest discover -s core -t .` — `core/` n'avait AUCUN test
avant ce lot ; les deux gates établies (direction_non_vie, normes) ne le
couvrent donc pas.
"""
import os
import re
import unittest

from core.frontiere_llm import (
    MODELE_ETABLI, MODELE_RECENT, MODELES_CONNUS, SITES, VARIABLE_CLE,
    FrontiereLLMIndisponible, appeler, chemins_appelants, cle_api,
    sites_du_modele, texte_des_blocs, texte_du_premier_bloc)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Le seul fichier autorisé à instancier le client, plus les tests qui le
# simulent. Toute autre occurrence est le défaut que ce lot supprime.
FICHIERS_AUTORISES = ('core/frontiere_llm.py', 'core/test_frontiere_llm.py')

IGNORES = ('.venv', 'venv', 'site-packages', '__pycache__', '.git')

# ⚠️ `anthropic.Anthropic(` ET `messages.create` : les deux, parce qu'un site
# pourrait garder le client d'un autre. `import anthropic` reste permis — deux
# appelants s'en servent pour NOMMER des types d'exception, ce qui ne fait
# sortir aucune donnée.
INSTANCIATION = re.compile(r'anthropic\s*\.\s*Anthropic\s*\(')
APPEL_SORTANT = re.compile(r'messages\s*\.\s*create\s*\(')


def _fichiers_python():
    for base, dossiers, fichiers in os.walk(RACINE):
        dossiers[:] = [d for d in dossiers if d not in IGNORES]
        for nom in fichiers:
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(base, nom)
            yield os.path.relpath(chemin, RACINE).replace('\\', '/'), chemin


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


class _Bloc:
    def __init__(self, texte, type_='text'):
        self.text = texte
        self.type = type_


class _Reponse:
    def __init__(self, *blocs):
        self.content = list(blocs)


class T1_LeVerrou(unittest.TestCase):
    """T1 — sans lui, un quatorzième site contredirait la garantie."""

    def test_aucun_site_n_instancie_le_client_hors_frontiere(self):
        """⚠️ C'EST LE TEST QUI PORTE TOUT LE CHANTIER. Une politique de
        confidentialité ne se garantit pas si elle est réimplémentable."""
        fautifs = [rel for rel, chemin in _fichiers_python()
                   if rel not in FICHIERS_AUTORISES
                   and INSTANCIATION.search(_lire(chemin))]
        self.assertEqual(fautifs, [], 'instanciation hors frontière : %s'
                         % ', '.join(fautifs))
        print('    OK T1 : aucune instanciation de client hors '
              'core/frontiere_llm.py')

    def test_aucun_appel_sortant_hors_frontiere(self):
        fautifs = [rel for rel, chemin in _fichiers_python()
                   if rel not in FICHIERS_AUTORISES
                   and APPEL_SORTANT.search(_lire(chemin))]
        self.assertEqual(fautifs, [], 'appel sortant hors frontière : %s'
                         % ', '.join(fautifs))
        print('    OK T1b : aucun messages.create hors frontière')

    def test_les_treize_sites_passent_bien_par_la_frontiere(self):
        """Le relevé n'est pas déclaratif : chaque site nommé doit exister et
        importer la frontière, sinon la table ment."""
        manquants = []
        for rel in chemins_appelants():
            chemin = os.path.join(RACINE, rel.replace('/', os.sep))
            if not os.path.exists(chemin):
                manquants.append(f'{rel} (absent)')
            elif 'frontiere_llm' not in _lire(chemin):
                manquants.append(f'{rel} (n\'importe pas la frontière)')
        self.assertEqual(manquants, [], '; '.join(manquants))
        print(f'    OK T1c : les {len(SITES)} sites passent par la frontière')


class T2_LaSourceUniqueDesModeles(unittest.TestCase):
    """T2 — trois sources d'identifiant avant ce lot, une seule après."""

    def test_plus_aucun_identifiant_de_modele_en_dur(self):
        """⚠️ RELEVÉ, PAS LISTE : on cherche la CHAÎNE, où qu'elle soit."""
        motif = re.compile(r'["\']claude-[a-z0-9.-]+["\']')
        fautifs = []
        for rel, chemin in _fichiers_python():
            if rel in FICHIERS_AUTORISES:
                continue
            if motif.search(_lire(chemin)):
                fautifs.append(rel)
        self.assertEqual(fautifs, [], 'identifiant en dur : %s'
                         % ', '.join(fautifs))
        print('    OK T2 : plus aucun identifiant de modèle hors frontière')

    def test_la_repartition_est_celle_du_releve(self):
        """Trois sites récents, dix établis. Toute dérive future déplace ce
        compte et fait tomber le test."""
        self.assertEqual(len(sites_du_modele(MODELE_RECENT)), 3)
        self.assertEqual(len(sites_du_modele(MODELE_ETABLI)), 10)
        self.assertEqual(len(SITES), 13)
        self.assertEqual(len({s.chemin for s in SITES}), 13)
        with self.assertRaises(KeyError):
            sites_du_modele('claude-invente')
        print('    OK T2b : 3 sites sur %s, 10 sur %s'
              % (MODELE_RECENT, MODELE_ETABLI))

    def test_la_coupure_n_est_pas_narration_contre_correspondance(self):
        """⚠️ LE RELEVÉ A CORRIGÉ MON HYPOTHÈSE. Une narration porte le
        modèle récent : la coupure est chronologique, pas fonctionnelle."""
        usages = {s.usage for s in sites_du_modele(MODELE_RECENT)}
        self.assertIn('narration', usages)
        self.assertIn('correspondance de colonnes', usages)
        print('    OK T2c : le modèle récent porte DEUX usages — la coupure '
              'est chronologique')


class T3_LAppel(unittest.TestCase):
    """T3 — ce qui part, et ce qui ne part pas."""

    def setUp(self):
        self.avant = os.environ.get(VARIABLE_CLE)
        os.environ[VARIABLE_CLE] = 'cle-de-test'

    def tearDown(self):
        if self.avant is None:
            os.environ.pop(VARIABLE_CLE, None)
        else:
            os.environ[VARIABLE_CLE] = self.avant

    def test_un_modele_inconnu_est_refuse_avant_tout_appel(self):
        """Refuser AVANT d'atteindre le réseau : une faute de frappe ne doit
        pas devenir une requête facturée."""
        with self.assertRaises(FrontiereLLMIndisponible) as ctx:
            appeler(modele='claude-invente', systeme='s', messages=[],
                    max_tokens=10)
        self.assertIn('inconnu', str(ctx.exception))
        print('    OK T3 : un modèle inconnu est refusé avant le réseau')

    def test_sans_cle_la_frontiere_leve_et_ne_sort_pas(self):
        os.environ.pop(VARIABLE_CLE, None)
        with self.assertRaises(FrontiereLLMIndisponible):
            cle_api()
        self.assertEqual(cle_api('explicite'), 'explicite')
        print('    OK T3b : sans clé, aucune sortie ; la valeur explicite '
              'prime sur l\'environnement')

    def test_la_cle_explicite_prime_sur_l_environnement(self):
        os.environ[VARIABLE_CLE] = 'environnement'
        self.assertEqual(cle_api('explicite'), 'explicite')
        self.assertEqual(cle_api(), 'environnement')
        self.assertEqual(cle_api(''), 'environnement')
        print('    OK T3c : les deux ordres de résolution restent chez '
              'leurs appelants')


class T4_LesDeuxLectures(unittest.TestCase):
    """T4 — elles diffèrent, et ce lot ne les unifie pas."""

    def test_sur_une_reponse_ordinaire_les_deux_concordent(self):
        r = _Reponse(_Bloc('le commentaire'))
        self.assertEqual(texte_du_premier_bloc(r), 'le commentaire')
        self.assertEqual(texte_des_blocs(r), 'le commentaire')
        print('    OK T4 : sur une réponse ordinaire, les deux lectures '
              'concordent')

    def test_elles_divergent_des_que_la_reponse_se_complique(self):
        """⚠️ LA DIFFÉRENCE EST RÉELLE ET ELLE EST CONSERVÉE. Unifier serait
        une amélioration, donc un changement de comportement, donc un autre
        lot."""
        r = _Reponse(_Bloc('', 'thinking'), _Bloc('la réponse'))
        self.assertEqual(texte_du_premier_bloc(r), '')
        self.assertEqual(texte_des_blocs(r), 'la réponse')
        r2 = _Reponse(_Bloc('a'), _Bloc('b'))
        self.assertEqual(texte_du_premier_bloc(r2), 'a')
        self.assertEqual(texte_des_blocs(r2), 'ab')
        print('    OK T4b : les deux lectures divergent sur une réponse à '
              'plusieurs blocs — écart conservé, non corrigé')


class T5_LaFrontiereNeSeSubstitueARien(unittest.TestCase):
    """T5 — ce lot est de structure ; il n'ajoute aucun jugement."""

    def test_les_erreurs_du_client_remontent_inchangees(self):
        """⚠️ DEUX APPELANTS DISTINGUENT LES EXCEPTIONS PAR LEUR TYPE
        (AuthenticationError, RateLimitError). Les envelopper changerait leur
        comportement : la frontière ne les touche pas."""
        source = _lire(os.path.join(RACINE, 'core', 'frontiere_llm.py'))
        corps = source.split('def appeler(')[1].split('\ndef ')[0]
        self.assertNotIn('except Exception', corps.replace(
            'except Exception as e:          # paquet absent', ''))
        self.assertEqual(len(MODELES_CONNUS), 2)
        print('    OK T5 : hors paquet absent, aucune exception n\'est '
              'capturée par la frontière')


if __name__ == '__main__':
    unittest.main(verbosity=2)
