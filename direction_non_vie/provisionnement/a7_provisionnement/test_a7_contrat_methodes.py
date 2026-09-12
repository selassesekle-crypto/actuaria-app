# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LE CONTRAT D'UNE METHODE QUI N'A PAS PU TOURNER
=============================================================================

 UNE MÉTHODE INDISPONIBLE DOIT DIRE DEUX CHOSES, ET LES DEUX DOIVENT
 S'ACCORDER : `disponible` dit qu'il n'y a pas de chiffre, et la valeur ne
 doit pas en être un.

 Relevé du 11/09/2026, dans les dictionnaires :

     benktander  disponible=False  reserve_totale=0.0    ← un faux zéro
     clark       disponible=True   reserve_totale=None   ← un contrat démenti

 ⚠️ AUCUN DOCUMENT NE PUBLIAIT CES VALEURS, ET C'EST MESURÉ. Le HTML et le
 Word écrivent « Benktander non calculée — elle se déduit de
 Bornhuetter-Ferguson, qui n'est pas disponible » et « Clark inapplicable —
 4 facteur(s) de développement sous 1 [...] la réserve n'est pas publiée ».
 Les rendus sont justes. Ce fichier ferme la TRAPPE, pas une fuite : un
 consommateur écrit demain qui lirait `reserve_totale` sans lire `disponible`
 publierait « 0 € », et un autre qui ferait l'inverse planterait sur `None`.

 ⚠️⚠️ LE DÉPÔT PORTE DÉJÀ LA DOCTRINE — `methodes_be.reserve()` rend `None` et
 non `0`, « NONE ET NON ZÉRO, C'EST TOUT L'INTÉRÊT ». Elle couvre les méthodes
 du Best Estimate ; Benktander et Clark n'en font pas partie. Encore une
 assiette qui s'arrête avant le défaut.
=============================================================================
"""
import io
import logging
import re
import unittest
import warnings
import zipfile

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)

#: ⚠️⚠️ ON NE COUPE PAS LES JOURNAUX A L IMPORT. Le correctif recu posait
#: `logging.disable(logging.CRITICAL)` en tete de module ; le depot
#: l INTERDIT et `core/test_journaux_importables.py::F5_LeDepotEntier`
#: echoue dessus. La raison est ecrite dans `test_a7_ibrahim` l.347 : ce
#: motif a deja MASQUE un `logger.error` reel et laisse une regression
#: survivre DEUX lots. La sourdine reste, BORNEE a la duree des tests.
_SOURDINE = None

#: Les sous-résultats de N3 qui portent une réserve et un drapeau.
_AVEC_CONTRAT = ('benktander', 'clark', 'bornhuetter_ferguson', 'cape_cod',
                 'munich', 'bz_ptf', 'glm_apc')

#: Les clés qui portent un montant. Un montant absent ne vaut pas zéro.
_MONTANTS = ('reserve_totale', 'reserve_best_estimate', 'ibnr_total',
             'reserve')


def _sans_exposition():
    from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
        GENINS,
    )
    return np.asarray(GENINS, dtype=float)


def _a_recours(n=7):
    C = np.zeros((n, n))
    for i in range(n):
        c = 100000.0 * (1 + 0.03 * i)
        for j in range(n - i):
            if j:
                c *= 0.90 if j % 3 else 1.10
            C[i, j] = c
    return C


def _run(C):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return AgentA7Provisionnement(verbose=False).run(
            source=C, mode_declare='cumule', n_sim_bootstrap=20, seed=42,
            generer_graphiques=False, generer_word=True, generer_html=True)


def setUpModule():
    """⚠️ LA SOURDINE EST BORNEE, ET POSEE AU NIVEAU DU MODULE.

    Le correctif recu coupait les journaux A L IMPORT.
    `core/test_journaux_importables.py::F5_LeDepotEntier` l interdit pour
    tout le depot, et la raison est ecrite dans `test_a7_ibrahim` l.347 : ce
    motif a deja MASQUE un `logger.error` reel et laisse une regression
    survivre DEUX lots (export Excel retombe a 0 octet).

    ⚠️ POURQUOI `setUpModule` ET NON `setUpClass`. Ce fichier definit deja un
    `setUpClass` ; la DERNIERE definition gagne, la mienne ne tournait donc
    jamais et `tearDownClass` recevait `None` — mesure : 3 erreurs sur 13
    tests. `setUpModule` n a pas ce probleme : unittest l appelle une fois,
    avant toute classe, et `tearDownModule` apres la derniere.
    """
    global _SOURDINE
    _SOURDINE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(_SOURDINE)


class T_Une_Methode_Indisponible_Ne_Chiffre_Pas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dossiers = [('GenIns sans exposition', _run(_sans_exposition())),
                        ('7x7 à recours', _run(_a_recours()))]

    def test_les_methodes_du_BE_passent_par_leur_accesseur_et_rendent_None(
            self):
        """⚠️⚠️ LA DOCTRINE EXISTE, ET ELLE A SON POINT D'ACCÈS.

        `methodes_be.reserve()` rend `None` — « NONE ET NON ZÉRO, C'EST TOUT
        L'INTÉRÊT ». Cape Cod et Bornhuetter-Ferguson posent bien `0.0` dans
        leur dictionnaire brut, et leur docstring le DIT : « La réserve à zéro
        n'est PAS le signal ». Le zéro est neutralisé par l'accesseur.

        ⚠️ MA PREMIÈRE VERSION MESURAIT LE DICTIONNAIRE BRUT ET ACCUSAIT CAPE
        COD. C'était une erreur d'assiette de ma part : le contrat de ces
        quatre méthodes n'est pas leur dictionnaire, c'est leur accesseur."""
        from direction_non_vie.provisionnement.a7_provisionnement.methodes_be import (
            ORDRE_AFFICHAGE, disponible, reserve,
        )
        vus, fautifs = 0, []
        for nom, r in self.dossiers:
            n3 = r.get('n3') or {}
            for m in ORDRE_AFFICHAGE:
                if disponible(n3, m):
                    continue
                vus += 1
                v = reserve(n3, m)
                if v is not None:
                    fautifs.append('%s / reserve(n3, %r) = %r alors que la '
                                   'méthode est indisponible' % (nom, m, v))
        self.assertGreater(vus, 0, 'aucune méthode du BE indisponible : rien '
                                   'n est mesuré')
        self.assertEqual(fautifs, [], '\n  '.join(fautifs))
        print('    OK CONTRAT-1 %d méthode(s) du BE indisponible(s), '
              'accesseur = None' % vus)

    def test_les_methodes_HORS_accesseur_ne_chiffrent_pas_leur_absence(self):
        """⚠️⚠️ LA VRAIE BRÈCHE, ET ELLE EST DE PÉRIMÈTRE.

        `methodes_be` couvre QUATRE méthodes — Chain Ladder, Mack,
        Bornhuetter-Ferguson, Cape Cod. Benktander, Clark, Munich, le GLM
        Poisson APC et Barnett-Zehnwirth n'ont PAS d'accesseur sanctionné :
        pour elles, le dictionnaire brut EST le contrat, et un `0.0` s'y lit
        « la réserve est nulle ».

        Encore une assiette qui s'arrête avant le défaut : la doctrine est
        juste, son point d'accès ne couvre pas la moitié des méthodes."""
        from direction_non_vie.provisionnement.a7_provisionnement.methodes_be import (
            ORDRE_AFFICHAGE,
        )
        couvertes = {'chain_ladder': 'chain_ladder', 'mack': 'mack',
                     'bornhuetter_ferguson': 'bf', 'cape_cod': 'cape_cod'}
        cles_couvertes = {couvertes[m] for m in ORDRE_AFFICHAGE
                          if m in couvertes}
        fautifs, vus = [], 0
        for nom, r in self.dossiers:
            for cle in _AVEC_CONTRAT:
                if cle in cles_couvertes:
                    continue
                bloc = (r.get('n3') or {}).get(cle)
                if not isinstance(bloc, dict):
                    continue
                if bloc.get('disponible') is not False:
                    continue
                vus += 1
                for k in _MONTANTS:
                    if k in bloc and isinstance(bloc[k], (int, float)) \
                            and not isinstance(bloc[k], bool):
                        fautifs.append(
                            '%s / n3[%r][%r] = %r alors que disponible=False, '
                            "et cette méthode n'a aucun accesseur qui "
                            'neutraliserait le zéro' % (nom, cle, k, bloc[k]))
        self.assertGreater(vus, 0, 'aucune méthode hors accesseur '
                                   'indisponible : rien n est mesuré')
        self.assertEqual(fautifs, [], '\n  '.join(fautifs))
        print('    OK CONTRAT-1b %d méthode(s) hors accesseur, aucun montant'
              % vus)

    def test_disponible_implique_un_montant_ou_un_motif(self):
        """⚠️ LE CONTRAT, DANS L'AUTRE SENS — et c'est celui que Clark
        démentait : `disponible=True` avec `reserve_totale=None`.

        On n'exige pas un chiffre : on exige qu'un consommateur puisse
        DISTINGUER. Si la valeur est absente, le bloc doit porter un motif
        lisible — sinon `disponible` ne veut rien dire."""
        fautifs, vus = [], 0
        for nom, r in self.dossiers:
            for cle in _AVEC_CONTRAT:
                bloc = (r.get('n3') or {}).get(cle)
                if not isinstance(bloc, dict) or bloc.get('disponible') is not True:
                    continue
                present = [k for k in _MONTANTS if k in bloc]
                if not present:
                    continue
                vus += 1
                if all(bloc[k] is None for k in present):
                    motif = str(bloc.get('message') or bloc.get('erreur') or '')
                    if not motif.strip():
                        fautifs.append(
                            '%s / n3[%r] : disponible=True, aucun montant, '
                            'aucun motif' % (nom, cle))
        self.assertGreater(vus, 0, 'aucune méthode disponible : rien mesuré')
        self.assertEqual(
            fautifs, [],
            'une méthode se déclare disponible sans chiffre ni motif :\n  '
            + '\n  '.join(fautifs))
        print('    OK CONTRAT-2 %d méthode(s) disponible(s), contrat tenu'
              % vus)

    def test_aucun_document_ne_publie_un_zero_pour_une_methode_absente(self):
        """⚠️⚠️ LA MESURE QUI COMPTE : les documents. Le contrat protège le
        consommateur de demain ; ce test protège le lecteur d'aujourd'hui."""
        for nom, r in self.dossiers:
            html = re.sub(r'<[^>]+>', ' ', r.get('html') or '')
            xml = zipfile.ZipFile(io.BytesIO(r['word_bytes'])).read(
                'word/document.xml').decode('utf-8', 'ignore')
            word = ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))
            for cle, etiquette in (('benktander', 'Benktander'),
                                   ('clark', 'Clark')):
                bloc = (r.get('n3') or {}).get(cle) or {}
                absente = (bloc.get('disponible') is False
                           or all(bloc.get(k) is None for k in _MONTANTS
                                  if k in bloc))
                if not absente:
                    continue
                for surface, txt in (('HTML', html), ('Word', word)):
                    for m in re.finditer(re.escape(etiquette), txt):
                        fen = txt[m.start():m.start() + 130]
                        with self.subTest(dossier=nom, methode=cle,
                                          surface=surface):
                            self.assertIsNone(
                                re.search(r'(^|[^0-9])0(\s|\u202f|&nbsp;)*'
                                          r'(€|EUR)', fen),
                                '%s publie un montant NUL pour %s, qui n a '
                                'pas pu être calculée : %r'
                                % (surface, etiquette, fen[:90]))
        print('    OK CONTRAT-3 aucun document ne chiffre une méthode absente')


if __name__ == '__main__':
    unittest.main(verbosity=1)
