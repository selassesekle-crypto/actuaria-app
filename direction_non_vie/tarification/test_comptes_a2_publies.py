"""Controles positifs — `a2/C1` et `a2/C2` : deux comptes publies a l'actuaire.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *un compte publie a l'actuaire doit etre celui de ce qui
s'est reellement passe.*

═══ CE QUE LE TRI A TROUVE ═══

Les deux constats etaient dans le TROISIEME ETAT que la regle de fermeture
nomme : **code corrige, aucun controle positif**. Ils comptaient donc OUVERTS,
et la feuille de route ne le savait pas. Meme etat que `a5/C5`, `conformite/C2`
et `conformite/C6` avant leur epinglage.

═══ `a2/C1` — UN COMPTE TOUJOURS NUL ═══

Le releve mesurait :

    winsorisation REELLE : 9 facteurs
    ACTUAIRE LIT >  Winsorisees  : 0 variable(s)

Cause : `winsor.get('colonnes_winsorisees', {})` sur un dictionnaire qui EST
DEJA celui des colonnes ecretees — la cle n'a jamais existe, le `.get` rendait
toujours `{}`. *Ce n'etait pas une mise en forme, c'etait le compte lui-meme.*

Mesure du 29/08 : « Winsorisees : **7** » pour **7** facteurs reellement
plafonnes. Le code lit desormais `len(winsor)`.

⚠️ ON N'EPINGLE PAS LE NOMBRE 7 : il depend du plan et du portefeuille. On
epingle l'EGALITE entre ce qui est ecrit et ce qui a ete fait. *Ce qui LIMITE
est sur, ce qui AFFIRME est une dette.*

═══ `a2/C2` — UNE PHRASE FAUSSE QUI PLAFONNAIT LE STATUT ═══

`_valider_sortie` comptait les colonnes `object` RESTANTES ; or A2 **ajoute**
les colonnes encodees et **conserve** la source. Chaque facteur categoriel
produisait donc un faux signalement, et le statut etait plafonne a AMBRE.

    20 plans, donnees COMPLETES et propres
    -> VERT atteint par 0/20 : AUCUN.  VERT etait STRUCTURELLEMENT inatteignable.

Correctif (lu au site) : le critere est devenu une propriete de la SORTIE —
une source est non encodee si AUCUNE colonne `<nom>_*` n'existe.

⚠️⚠️ ET LE PLAFONNEMENT N'A PAS ETE SUPPRIME, IL A ETE RENDU JUSTE. Une colonne
VRAIMENT non encodable doit TOUJOURS plafonner a AMBRE : les modeles ne
mangent pas de chaines de caracteres. *Un correctif qui aurait retire le
plafond aurait ferme le constat en detruisant le signal.* Les deux sens sont
mesures ci-dessous.
"""

from __future__ import annotations

import logging
import unittest
import warnings

from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)


def _executer(df):
    """A1 -> A2, le chemin de production. Rend le résultat d'A2.

    ⚠️ PAR A1, PAS PAR `fit`/`transform`. Les deux chemins ne traitent pas
    l'exposition nulle de la même façon (constat `a2/C5`) : mesurer sur le
    mauvais chemin donnerait une réponse vraie sur le mauvais objet.
    """
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                branche='non_vie', sous_branche='auto', dataframe=df)
            return AgentA2Preprocessing(
                models_path='/tmp', audit_path='/tmp', verbose=False).run(
                    result_a1=r1, plan=_PLAN_AUTO)
        finally:
            logging.disable(precedent)


def _validation(resultat) -> dict:
    return ((resultat.get('rapport') or {})
            .get('transformations', {}).get('validation', {}))


class TestLeCompteDeWinsorisees(unittest.TestCase):
    """`a2/C1` — ce qui est écrit est ce qui a été fait."""

    def test_le_nombre_ECRIT_est_le_nombre_REELLEMENT_ecrete(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — une ÉGALITÉ, pas un nombre.

        Le relevé mesurait « 0 » pour 9 facteurs écrêtés. On compare donc le
        chiffre publié au dictionnaire des colonnes réellement plafonnées, sans
        figer aucune valeur : elle dépend du plan et du portefeuille.
        """
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        winsor = ((r.get('rapport') or {})
                  .get('transformations', {}).get('winsorisation', {}))
        self.assertTrue(winsor, 'prémisse : le portefeuille doit faire écrêter')
        import re
        m = re.search(r'Winsorisées\s*:\s*(\d+) variable', str(r.get('commentaire')))
        self.assertIsNotNone(m, 'le commentaire ne publie plus le compte')
        self.assertEqual(
            int(m.group(1)), len(winsor),
            f"l actuaire lit {m.group(1)} alors que {len(winsor)} facteur(s) "
            f"ont ete ecretes")
        print(f"    A2-1 « Winsorisées : {m.group(1)} » pour {len(winsor)} "
              f"réellement écrêtées (le relevé lisait 0 pour 9)")

    def test_le_compte_n_est_JAMAIS_nul_quand_il_y_a_ecretement(self):
        """⚠️ LA FORME EXACTE DU DÉFAUT : `.get()` sur une clé inexistante rend
        `{}`, donc **toujours zéro**. Un compte qui ne peut que valoir 0 n'est
        pas un compte."""
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        winsor = ((r.get('rapport') or {})
                  .get('transformations', {}).get('winsorisation', {}))
        self.assertGreater(len(winsor), 0)
        self.assertNotIn('Winsorisées  : 0 variable', str(r.get('commentaire')))
        print(f"    A2-2 {len(winsor)} écrêtées et le commentaire ne dit plus 0")

    def test_chaque_entree_porte_ses_BORNES_et_son_compte(self):
        """⚠️ Le dictionnaire doit rester la SOURCE du compte, pas un décor.

        S'il perdait ses bornes, `len()` compterait encore — mais sur quoi ?
        """
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        winsor = ((r.get('rapport') or {})
                  .get('transformations', {}).get('winsorisation', {}))
        for nom, detail in winsor.items():
            with self.subTest(facteur=nom):
                for cle in ('borne_inf', 'borne_sup', 'n_valeurs_ecretees'):
                    self.assertIn(cle, detail)
        print(f"    A2-3 les {len(winsor)} entrées portent bornes et compte")


class TestLeCompteDeColonnesNonEncodees(unittest.TestCase):
    """`a2/C2` — la phrase est vraie, et le plafond reste juste."""

    def test_un_facteur_ENCODE_n_est_plus_signale_non_encode(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT.

        A2 AJOUTE les colonnes encodées et CONSERVE la source ; compter les
        `object` restantes signalait donc chaque facteur catégoriel.
        """
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        non_enc = _validation(r).get('colonnes_non_encodees')
        self.assertEqual(
            non_enc, [],
            f"des facteurs ENCODES sont encore signales non encodes : {non_enc}")
        print("    A2-4 données propres : 0 colonne signalée non encodée")

    def test_VERT_est_de_nouveau_ATTEIGNABLE(self):
        """⚠️⚠️ LA CONSÉQUENCE MESURÉE DU CONSTAT — « VERT atteint par 0/20 ».

        Un statut qu'aucun dossier ne peut atteindre ne gradue plus rien : il
        cesse d'être un signal, exactement comme un avertissement affiché
        toujours.
        """
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        self.assertEqual(
            r.get('statut_rag'), 'VERT',
            f"statut {r.get('statut_rag')} sur des donnees propres : VERT "
            f"redevient inatteignable")
        print("    A2-5 données propres → VERT (avant : structurellement "
              "inatteignable)")

    def test_SECOND_SENS_une_VRAIE_colonne_texte_plafonne_TOUJOURS(self):
        """⚠️⚠️ SECOND SENS, ET IL EST LE CŒUR DU LOT.

        Le correctif a rendu la liste JUSTE, il n'a pas retiré le plafond. Une
        colonne réellement non encodable doit toujours faire tomber à AMBRE —
        les modèles ne mangent pas de chaînes. *Un correctif qui aurait retiré
        le plafond aurait fermé le constat en détruisant le signal.*
        """
        df = _portefeuille_auto(500, seed=3).copy()
        df['commentaire_libre'] = [f'note {i}' for i in range(len(df))]
        r = _executer(df)
        non_enc = _validation(r).get('colonnes_non_encodees')
        self.assertIn('commentaire_libre', non_enc,
                      'une vraie colonne non encodable passe inapercue')
        self.assertEqual(r.get('statut_rag'), 'AMBRE',
                         'le plafond a ete RETIRE au lieu d etre rendu juste')
        print(f"    A2-6 second sens : une vraie colonne texte est signalée "
              f"({non_enc}) ET plafonne à AMBRE")

    def test_le_critere_porte_sur_la_SORTIE_pas_sur_la_source(self):
        """⚠️ LA FORME DU CORRECTIF, ÉPINGLÉE.

        Une source est non encodée **si aucune colonne `<nom>_*` n'existe**.
        Ce test le vérifie par l'effet : la source catégorielle est TOUJOURS
        présente en sortie — c'est voulu, le rapport en a besoin — et pourtant
        elle n'est plus signalée.

        ⚠️⚠️ ET CE TEST A ÉTÉ CORRIGÉ PAR SON PROPRE ÉCHEC. Il filtrait sur
        `dtype == object` ; mesuré, les colonnes sortent en **dtype `str`** —
        c'est-à-dire exactement l'hypothèse que le `Pandas4Warning` de ce même
        module dénonce, et dans laquelle ma sonde est tombée. On teste
        désormais « **pas numérique** », qui est la propriété réellement
        voulue et qui survit au changement de dtype.
        """
        import pandas as pd
        r = _executer(_portefeuille_auto(500, seed=3).copy())
        X = r.get('dataframe')
        sources = [c for c in X.columns
                   if not pd.api.types.is_numeric_dtype(X[c]) and any(
                       str(o).startswith(c + '_') for o in X.columns)]
        self.assertTrue(
            sources,
            'prémisse : au moins une source catégorielle doit être conservée')
        for c in sources:
            self.assertNotIn(c, _validation(r).get('colonnes_non_encodees') or [])
        print(f"    A2-7 {len(sources)} source(s) conservée(s) en sortie, "
              f"aucune signalée : le critère porte sur la SORTIE")


if __name__ == '__main__':
    unittest.main()
