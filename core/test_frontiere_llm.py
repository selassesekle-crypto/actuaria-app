# -*- coding: utf-8 -*-
"""Tests C1 — la frontière unique, et le verrou qui la rend vraie.

⚠️ GATE : `py -m unittest discover -s core -t .` — `core/` n'avait AUCUN test
avant ce lot ; les deux gates établies (direction_non_vie, normes) ne le
couvrent donc pas.
"""
import os
import re
import unittest
from unittest.mock import patch

from core.frontiere_llm import (
    MODELE_ETABLI, MODELE_RECENT, MODELES_CONNUS, PARAMETRES_REFUSES, SITES,
    VARIABLE_CLE, FrontiereLLMIndisponible, ReponseInexploitable,
    RequeteRefusee, appeler, chemins_appelants, cle_api, sites_du_modele,
    texte_des_blocs)

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


def _payload_transmis(**kwargs):
    """Ce que la frontière transmet RÉELLEMENT au client, client simulé.

    ⚠️ AUCUN TEST DE CE DÉPÔT NE DOIT ATTEINDRE LE RÉSEAU. Le paquet
    `anthropic` a été installé en cours de route ; s'appuyer sur son absence
    n'est donc pas une garantie — on simule.
    """
    vus = {}

    class _Messages:
        def create(self, **kw):
            vus.update(kw)
            return _Reponse(_Bloc('reponse simulee'))

    class _Client:
        def __init__(self, **_):
            self.messages = _Messages()

    with patch('anthropic.Anthropic', _Client):
        appeler(systeme='s', messages=[{'role': 'user', 'content': 'x'}],
                **kwargs)
    return vus


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


class T4_LaLectureUnique(unittest.TestCase):
    """T4 — il y avait deux lectures, la divergence était une panne.

    ⚠️ MESURÉ À L'USAGE : six appels ont abouti en 200 OK et leurs six
    réponses ont été JETÉES, parce que `content[0].text` lève dès que le
    premier bloc n'est pas du texte. J'avais documenté cet écart en C1 en le
    classant « amélioration » — c'était un mauvais classement.
    """

    def test_l_ancienne_lecture_n_existe_plus(self):
        """Laisser les deux, c'était laisser le piège."""
        import core.frontiere_llm as f
        self.assertFalse(hasattr(f, 'texte_du_premier_bloc'))
        # Ce fichier est exclu : il NOMME l'ancienne lecture pour vérifier
        # qu'elle a disparu, comme T1 et T2 s'excluent pour la même raison.
        fautifs = [rel for rel, chemin in _fichiers_python()
                   if rel != 'core/test_frontiere_llm.py'
                   and 'texte_du_premier_bloc' in _lire(chemin)]
        self.assertEqual(fautifs, [], '; '.join(fautifs))
        print('    OK T4 : l\'ancienne lecture a disparu du dépôt entier')

    def test_un_seul_bloc_de_texte_rend_le_texte(self):
        """La forme ordinaire : identique à ce que rendait l'ancienne."""
        self.assertEqual(texte_des_blocs(_Reponse(_Bloc('le commentaire'))),
                         'le commentaire')
        self.assertEqual(texte_des_blocs(_Reponse(_Bloc('a'), _Bloc('b'))),
                         'ab')
        print('    OK T4b : un bloc de texte → le texte ; deux → concaténés')

    def test_un_bloc_de_raisonnement_EN_TETE_ne_fait_plus_perdre_la_reponse(self):
        """⚠️ LE CAS QUI A COÛTÉ SIX RÉPONSES. Un bloc de raisonnement porte
        `.thinking`, pas `.text` : l'ancienne lecture levait."""
        r = _Reponse(_Bloc(None, 'thinking'), _Bloc('la réponse'))
        self.assertEqual(texte_des_blocs(r), 'la réponse')
        print('    OK T4c : raisonnement en tête → la réponse est récupérée')

    def test_une_reponse_sans_texte_LEVE_au_lieu_de_rendre_du_vide(self):
        """⚠️ SANS CELA ON ÉCHANGERAIT UNE PANNE MUETTE CONTRE UNE AUTRE :
        une narration VIDE étiquetée « venue de l'API »."""
        for reponse, attendu in (
                (_Reponse(), 'aucun bloc'),
                (_Reponse(_Bloc(None, 'thinking')), 'thinking'),
                (_Reponse(_Bloc('   ')), 'text')):
            with self.assertRaises(ReponseInexploitable) as ctx:
                texte_des_blocs(reponse)
            self.assertIn(attendu, str(ctx.exception))
        print('    OK T4d : réponse vide, raisonnement seul ou texte blanc → '
              'ReponseInexploitable, jamais une chaîne vide')

    def test_le_message_nomme_les_TYPES_jamais_le_contenu(self):
        """Diagnostiquer sans divulguer : c'est la règle de C2."""
        with self.assertRaises(ReponseInexploitable) as ctx:
            texte_des_blocs(_Reponse(_Bloc('SECRET_DU_CLIENT', 'thinking')))
        message = str(ctx.exception)
        self.assertIn('thinking', message)
        self.assertNotIn('SECRET_DU_CLIENT', message)
        print('    OK T4e : le message nomme les types, pas le contenu')


class T7_LesTroisCauses(unittest.TestCase):
    """T7 — F2 : un message qui désigne la mauvaise cause est pire que rien."""

    def test_les_trois_causes_sont_des_types_distincts(self):
        self.assertTrue(issubclass(ReponseInexploitable,
                                   FrontiereLLMIndisponible))
        self.assertTrue(issubclass(RequeteRefusee, FrontiereLLMIndisponible))
        self.assertFalse(issubclass(ReponseInexploitable, RequeteRefusee))
        self.assertFalse(issubclass(RequeteRefusee, ReponseInexploitable))
        print('    OK T7 : environnement / requête refusée / réponse '
              'inexploitable — trois types, une famille')

    def test_plus_aucun_site_n_accuse_l_API_d_une_panne(self):
        """⚠️ LE DÉPÔT PORTAIT DÉJÀ LA TRACE DU MÊME MOTIF : le commentaire
        d'en-tête de `n5_rapport.py` raconte un défaut de code journalisé
        comme « Claude API indisponible ». C'était la troisième fois."""
        motif = re.compile(r'warning\([^)]*Claude API[^)]*\)')
        fautifs = [rel for rel, chemin in _fichiers_python()
                   if motif.search(_lire(chemin))]
        self.assertEqual(fautifs, [], 'accuse encore l\'API : %s'
                         % ', '.join(fautifs))
        print('    OK T7b : plus aucun journal n\'accuse l\'API d\'une panne')


class T6_LaCombinaisonRefusee(unittest.TestCase):
    """T6 — le défaut qui a fait taire trois sites, et son verrou.

    ⚠️ MESURÉ CONTRE L'API le 2026-08-07 : `claude-sonnet-5` refuse
    `temperature` (400, « deprecated for this model »), quelle que soit sa
    valeur. Trois sites du dépôt associaient les deux ; leurs appels étaient
    TOUS rejetés, et l'un d'eux — en production — repliait en silence.
    """

    def setUp(self):
        self.avant = os.environ.get(VARIABLE_CLE)
        os.environ[VARIABLE_CLE] = 'cle-de-test'

    def tearDown(self):
        if self.avant is None:
            os.environ.pop(VARIABLE_CLE, None)
        else:
            os.environ[VARIABLE_CLE] = self.avant

    def test_la_combinaison_est_refusee_AVANT_le_reseau(self):
        """Le paquet `anthropic` est absent ici : si la frontière atteignait
        l'import, l'erreur porterait sur le paquet. Elle porte sur le
        paramètre — donc le refus précède bien toute tentative."""
        with self.assertRaises(RequeteRefusee) as ctx:
            appeler(modele=MODELE_RECENT, systeme='s', messages=[],
                    max_tokens=10, temperature=0.0)
        message = str(ctx.exception)
        self.assertIn('temperature', message)
        self.assertIn(MODELE_RECENT, message)
        self.assertNotIn('anthropic', message)
        print('    OK T6 : la combinaison est refusée avant le réseau')

    def test_le_refus_ne_depend_pas_de_la_valeur(self):
        """⚠️ « DÉPRÉCIÉ POUR CE MODÈLE » N'EST PAS « VALEUR NON-DÉFAUT
        REFUSÉE » : 0.0, 1.0 ou 0.7 sont refusées de la même façon."""
        for valeur in (0.0, 0.7, 1.0):
            with self.assertRaises(RequeteRefusee):
                appeler(modele=MODELE_RECENT, systeme='s', messages=[],
                        max_tokens=10, temperature=valeur)
        print('    OK T6b : refus indépendant de la valeur (0.0, 0.7, 1.0)')

    def test_sans_le_parametre_la_frontiere_laisse_passer(self):
        """Ne pas transmettre le paramètre est la correction, et on vérifie la
        CHARGE UTILE elle-même : `temperature` n'y figure plus.

        ⚠️ LE CLIENT EST SIMULÉ. Aucun test de ce dépôt ne doit atteindre le
        réseau — j'ai écrit ces tests en supposant le paquet absent, il a été
        installé depuis, et deux d'entre eux ont réellement tenté un appel.
        """
        vus = _payload_transmis(modele=MODELE_RECENT, max_tokens=10)
        self.assertNotIn('temperature', vus)
        self.assertEqual(vus['model'], MODELE_RECENT)
        print('    OK T6c : sans le paramètre, la requête part sans lui')

    def test_l_autre_modele_accepte_toujours_le_parametre(self):
        """Le refus est attaché à UN modèle, pas posé en règle générale."""
        self.assertNotIn(MODELE_ETABLI, PARAMETRES_REFUSES)
        vus = _payload_transmis(modele=MODELE_ETABLI, max_tokens=10,
                                temperature=0.0)
        self.assertEqual(vus['temperature'], 0.0)
        print(f'    OK T6d : {MODELE_ETABLI} accepte toujours temperature')

    def test_un_repli_d_environnement_n_est_pas_un_repli_sur_defaut(self):
        """⚠️ C'EST LA DISTINCTION QUI MANQUAIT ET QUI A PERMIS LE SILENCE.
        RequeteRefusee HÉRITE de FrontiereLLMIndisponible : tout appelant qui
        capturait déjà celle-ci continue de la capturer — la distinction
        s'ajoute sans casser personne."""
        self.assertTrue(issubclass(RequeteRefusee, FrontiereLLMIndisponible))
        self.assertIsNot(RequeteRefusee, FrontiereLLMIndisponible)
        print('    OK T6e : RequeteRefusee se distingue sans rien casser')

    def test_aucun_site_ne_reintroduit_le_parametre_refuse(self):
        """⚠️ LE VERROU. Dans les sources des sites qui portent le modèle
        concerné, toute constante de température doit valoir None."""
        import ast
        fautifs = []
        for site in sites_du_modele(MODELE_RECENT):
            chemin = os.path.join(RACINE, site.chemin.replace('/', os.sep))
            arbre = ast.parse(_lire(chemin))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Assign):
                    continue
                for cible in noeud.targets:
                    if (isinstance(cible, ast.Name)
                            and 'TEMPERATURE' in cible.id.upper()):
                        valeur = noeud.value
                        if not (isinstance(valeur, ast.Constant)
                                and valeur.value is None):
                            fautifs.append(f'{site.chemin}::{cible.id}')
        self.assertEqual(fautifs, [], 'température réintroduite : %s'
                         % ', '.join(fautifs))
        print(f'    OK T6f : les {len(sites_du_modele(MODELE_RECENT))} sites '
              f'du modèle concerné ne transmettent aucune température')

    def test_la_provenance_de_la_mesure_est_dans_la_donnee(self):
        """Une entrée sans mesure n'a rien à faire dans cette table."""
        source = _lire(os.path.join(RACINE, 'core', 'frontiere_llm.py'))
        bloc = source.split('PARAMETRES_REFUSES')[0][-1200:]
        for attendu in ('2026-08-07', '400', 'deprecated for this model'):
            self.assertIn(attendu, bloc, attendu)
        self.assertEqual(PARAMETRES_REFUSES[MODELE_RECENT], ('temperature',))
        print('    OK T6g : la mesure et sa date accompagnent la table')


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
