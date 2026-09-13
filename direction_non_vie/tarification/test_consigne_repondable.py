r"""
==============================================================================
  UNE CONSIGNE QUI NE PEUT PAS RECEVOIR DE REPONSE EST PIRE QU'UN SILENCE
==============================================================================

⚠️⚠️ `EFF-1` -- LE REMEDE PRESCRIT ETAIT INAPPLICABLE AU CAS QUE LE MODULE
INVITE LUI-MEME. Le garde-fou n.4 ecarte une colonne sur sa correlation
avec la cible. `synthese_exclusions` publie alors ACTION REQUISE, nomme
honnetement le faux positif -- << elle ne distingue pas une fuite d'une
variable de VOLUME legitime >> -- et prescrit le remede : declarer la
colonne `anteriorite=True` au plan. L'actuaire le fait. Et
`synthese_exemptions_effet` lui repondait :

    << VERIFIEZ que chacune porte bien sur le PASSE >>

Or une taille de flotte, un effectif, un chiffre d'affaires ne portent
PAS sur le passe : ils sont ARRETES a la souscription. *L'actuaire
consciencieux ne peut ni repondre oui ni repondre non -- et s'il repond
non, il conclut que l'exemption qu'on vient de lui prescrire est
injustifiee.*

⚠️⚠️ CE FICHIER SURVEILLE LA BOUCLE, PAS UNE PHRASE. Le texte qui INVITE
et le texte qui VERIFIE sont ecrits a deux endroits differents, par deux
fonctions differentes, et rien ne les obligeait a parler de la meme
chose. `EX-3` exige qu'ils couvrent les MEMES natures. *C'est
l'asymetrie entre voisins qui revele ce genre de defaut, et elle se
mesure.*

⚠️ CE QUI N'EST PAS TOUCHE, ET C'EST DELIBERE : ni le seuil, ni le
mecanisme, ni le nom du champ `anteriorite`. Renommer le champ casserait
les plans signes qui le portent ; poser un seuil par nature serait
inventer un chiffre actuariel que personne n'a signe. Seul le TEXTE
change.

⚠️⚠️ ET IL EXISTE UN SECOND ENDROIT QUI POSE LA MEME QUESTION, QUI EST
LEGITIME. `detecter_fuites_par_effet` ecrit << Verifiez toutefois
qu'elles portent bien sur le PASSE >> -- mais son message ne s'adresse
qu'a `signaux_experience`, rempli SI ET SEULEMENT SI
`_est_experience_passee(c)`. Mesure du 13/09/2026 : 7 variables de
VOLUME sur 7 rendent `False`, 5 variables d'EXPERIENCE sur 5 rendent
`True`. *Pour son audience, la question EST repondable.* `EX-5` garde
cette distinction : effacer la difference entre les deux audiences
serait corriger un texte juste.
==============================================================================
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core import conformite_reglementaire as CR

#: Les deux natures que le mecanisme fait entrer -- le module les nomme
#: lui-meme dans `synthese_exclusions`.
_VOLUME = ('taille_flotte', 'log_taille_flotte', 'effectif', 'nb_salaries',
           'ca_annuel_eur', 'surface_m2', 'nb_vehicules')
_EXPERIENCE = ('antecedents_sinistres_n1', 'nb_sinistres_anterieurs',
               'risque_historique', 'antecedents_sinistres_3ans',
               'sinistres_passes')


class TestUneConsigneRepondable(unittest.TestCase):

    def test_EX1_SCEAU_la_consigne_nomme_le_CRITERE_et_non_le_PASSE(self):
        """⚠️⚠️ LE SCEAU. La consigne doit poser un critere VERIFIABLE pour
        les deux natures. Celui que le module applique deja : la valeur
        est-elle FIXEE A LA DATE D'EFFET ?"""
        texte = CR.synthese_exemptions_effet(
            {'taille_flotte': {}, 'antecedents_sinistres_n1': {}})
        self.assertIsNotNone(texte, 'aucun texte publie sur une exemption')
        self.assertIn(
            "FIXÉE À LA DATE D'EFFET", texte,
            f"la consigne ne nomme pas le critere commun aux deux natures : "
            f"{texte[-200:]!r}")
        #: ⚠️ ET LA QUESTION INAPPLICABLE NE DOIT PLUS ETRE POSEE SEULE.
        #: << porte bien sur le PASSE >> reste admissible SI elle est
        #: attachee a la nature EXPERIENCE, jamais comme consigne unique.
        self.assertNotIn(
            'VÉRIFIEZ que chacune porte bien sur le PASSÉ', texte,
            'la consigne inapplicable est de retour telle quelle')
        print(f"    EX-1 SCEAU : la consigne nomme le critere, "
              f"{len(texte)} caracteres publies")

    def test_EX2_SCEAU_les_DEUX_natures_sont_nommees_et_distinguees(self):
        """⚠️⚠️ LE POINT EXACT DU CONSTAT. Le champ recoit DEUX natures et la
        question ne se pose pas de la meme facon pour chacune : une variable
        d'experience doit porter sur une periode CLOSE avant l'effet, une
        variable de volume doit etre celle DECLAREE a la souscription. *Un
        texte qui n'en nomme qu'une laisse l'autre sans reponse.*"""
        texte = CR.synthese_exemptions_effet({'taille_flotte': {}})
        for attendu in ('VOLUME', 'EXPÉRIENCE PASSÉE', 'SOUSCRIPTION'):
            self.assertIn(
                attendu, texte,
                f"la consigne ne nomme pas {attendu!r} : la moitie des cas "
                f"que le mecanisme recoit reste sans critere")
        print('    EX-2 SCEAU : les deux natures sont nommees et '
              'distinguees')

    def test_EX3_SCEAU_le_texte_qui_INVITE_et_celui_qui_VERIFIE_saccordent(
            self):
        """⚠️⚠️ LE SCEAU DE LA BOUCLE, ET C'EST LUI QUI COMPTE. Deux
        fonctions ecrivent les deux bouts d'une meme instruction :
        `synthese_exclusions` INVITE a declarer une exemption,
        `synthese_exemptions_effet` demande de la VERIFIER. Rien ne les
        obligeait a parler de la meme chose -- et c'est precisement par la
        que le defaut est entre. *Si l'une nomme deux natures et l'autre
        une seule, l'actuaire recoit une question sans reponse.*"""
        invite = CR.synthese_exclusions(
            {'taille_flotte': "FUITE DÉTECTÉE PAR L'EFFET — signal mesuré"})
        verifie = CR.synthese_exemptions_effet({'taille_flotte': {}})
        self.assertIsNotNone(invite)
        self.assertIsNotNone(verifie)
        #: ⚠️ LE CRITERE DE L'ACCORD EST MESURE, PAS DEVINE : la nature que
        #: l'INVITATION nomme doit se retrouver dans la VERIFICATION.
        manquantes = [n for n in ('VOLUME',)
                      if n in invite and n not in verifie]
        self.assertEqual(
            manquantes, [],
            f"la consigne d'INVITATION nomme {manquantes} et celle de "
            f"VERIFICATION ne la nomme pas : l'actuaire est invite a "
            f"declarer une nature dont on ne lui dit pas comment la "
            f"verifier.\n  invitation  : {invite[:150]}\n"
            f"  verification : {verifie[:150]}")
        #: ⚠️ ET LES DEUX DOIVENT PARLER DU MEME MOMENT. L'une dit
        #: << connue au moment de tarifer un contrat neuf >>, l'autre
        #: << fixee a la date d'effet >> : c'est le meme critere, et il doit
        #: rester reconnaissable des deux cotes.
        self.assertIn('connue au moment de tarifer', invite)
        self.assertIn("DATE D'EFFET", verifie)
        print('    EX-3 SCEAU : invitation et verification couvrent les '
              'memes natures, et le meme instant de reference')

    def test_EX4_CONTRE_EPREUVE_aucune_exemption_aucune_phrase(self):
        """⚠️ LE SECOND SENS. Une consigne publiee a tous les coups devient
        un avertissement permanent, donc un avertissement qu'on cesse de
        lire. Sans exemption, la fonction doit rendre `None`."""
        for vide in (None, {}):
            self.assertIsNone(
                CR.synthese_exemptions_effet(vide),
                f'un texte est publie sur {vide!r} : la consigne parle '
                f'alors qu il n y a rien a verifier')
        print('    EX-4 contre-epreuve : aucune exemption -> aucune phrase')

    def test_EX5_CONTRE_EPREUVE_les_deux_audiences_restent_distinctes(self):
        """⚠️⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER. Un second endroit
        du module pose la MEME question -- et il a raison de la poser, parce
        que son audience est differente. `signaux_experience` n'est rempli
        que si `_est_experience_passee(c)`. *Effacer la difference entre les
        deux audiences serait corriger un texte juste.*"""
        for c in _VOLUME:
            self.assertFalse(
                CR._est_experience_passee(c),
                f"`{c}` est classee EXPERIENCE PASSEE : une variable de "
                f"VOLUME recevrait alors la consigne du passe, qui ne lui "
                f"convient pas")
        for c in _EXPERIENCE:
            self.assertTrue(
                CR._est_experience_passee(c),
                f"`{c}` n'est plus classee experience passee : elle partirait "
                f"en FUITE au lieu d'etre signalee")
        print(f"    EX-5 contre-epreuve : {len(_VOLUME)} variables de volume "
              f"hors experience, {len(_EXPERIENCE)} variables d experience "
              f"reconnues")


if __name__ == '__main__':
    unittest.main(verbosity=2)
