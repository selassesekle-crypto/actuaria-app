"""LA SENTINELLE DE LA PORTEE — UN FAIT QUI N'ATTEINT AUCUN DOCUMENT.

⚠️⚠️ CE MODULE EXISTE PARCE QUE `PUBLICATION-1` DIT QU'IL EST ABSENT, ET
LE CONSTAT EST MESURE : sur les **63 faits** rendus par la chaine a1..a6,
**17 n'atteignent AUCUNE surface signee** et **26 n'en atteignent qu'UNE
SEULE** -- dont vingt-deux fois l'Excel de l'agent lui-meme.
*L'Excel d'agent est un faux reconfort : le fait y est visible, et
personne ne le signe.*

Le depot a diagnostique cette cause DEUX FOIS -- le 03/09 pour trois
reserves, le 12/09 pour une quatrieme -- et l'a corrigee **a la main, par
hasard, a chaque fois**. Ce qui manquait n'etait pas un correctif : c'est
l'instrument qui ENUMERE, et la sentinelle qui REMESURE.

⚠️⚠️ POURQUOI ELLE REMESURE AU LIEU DE RELIRE UNE REFERENCE.
`reference_gel.json` porte la lecon, mot pour mot :

    « C'était un INSTRUMENT, pas une SENTINELLE — le seul manque
      structurel sur lequel DEUX audits independants tombent d'accord. »

Une reference qu'un script regenere, mais que rien ne verifie a chaque
gate, laisse passer une degradation commitee. **Une portee peut se
degrader sans qu'aucun producteur change** : il suffit qu'un service
cesse de lire une cle. Un controle purement statique -- << tout
producteur trouve par AST figure dans la reference >> -- ne voit PAS ce
cas. C'est pourquoi ce module produit sa chaine et remesure.

⚠️ CE QU'IL COUTE, ET C'EST ASSUME : une chaine complete, ~95 s. Le
chantier `chantier-temps-execution` a clos la question du cout en temps ;
la seule objection serieuse contre la remesure tombe avec elle.

⚠️ ET AUCUN CACHE N'EST POSE. Garder la chaine -- dataframes, modeles,
documents -- vivante pendant toute la gate n'est pas gratuit : ce
chantier a paye DEUX `MemoryError`. La chaine vit dans `setUpClass` et
meurt avec la classe.

CE QUE CE MODULE NE FAIT PAS : **il ne publie AUCUN fait.** Aucun
document ne bouge, le gel ne bouge pas, aucun euro ne bouge. Publier est
la partie 2, et elle attend son arbitrage.

Les exigences :
  MFS-1  la reference EXISTE, est publiable, declare son JEU et ce
         qu'elle NE couvre PAS
  MFS-2  le JEU du lanceur n'a pas change depuis le figeage
  MFS-3  LA DETTE EST PLAFONNEE : un fait NEUF a <= 1 surface mord
  MFS-4  AUCUNE PORTEE NE SE DEGRADE, remesuree fait par fait
  MFS-5  aucun fait de la reference n'a disparu du releve sans le dire
  MFS-6  le plafond ne se releve pas en silence : code ET reference
  MFS-7  le TEMOIN : l'assiette n'est pas vide, et l'exclusion d'A7
         retranche encore quelque chose

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, os.path.join(_RACINE, 'scripts')):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import matrice_fait_surface as M

_REFERENCE = pathlib.Path(_ICI) / 'reference_matrice.json'


def _reference() -> dict:
    return json.loads(_REFERENCE.read_text(encoding='utf-8'))


class TestMatriceFaitSurface(unittest.TestCase):
    """⚠️ UNE SEULE CHAINE POUR TOUTE LA CLASSE, et elle meurt avec elle."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        cls.ref = _reference()
        cls.mesure = M.mesurer()
        cls.faits = {f['chemin']: f for f in cls.mesure['faits']}

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)
        #: ⚠️ ON LIBERE EXPLICITEMENT : dataframes, modeles et documents.
        cls.mesure = cls.faits = None

    # ── MFS-1 ────────────────────────────────────────────────────────────
    def test_MFS1_la_reference_existe_et_DECLARE_ce_qu_elle_ne_couvre_pas(self):
        """⚠️ *Un releve sans son assiette se relit faux six jours plus
        tard.* Une reference qui ne dit pas ses limites les fait oublier."""
        for cle in ('_doctrine', '_assiette_non_couverte', '_trois_etats',
                    'jeu', 'plafond_dette', 'nb_faits', 'faits'):
            self.assertIn(cle, self.ref, f'la reference ne porte pas {cle!r}')
        self.assertGreater(
            len(self.ref['_assiette_non_couverte']), 150,
            "l'assiette non couverte tient en une ligne : elle ne dit "
            'probablement pas tout ce qu'"'"'elle omet')
        self.assertEqual(
            sorted(self.ref['_trois_etats']), sorted((M.PORTE, M.ABSENT,
                                                      M.MUET)),
            'les TROIS etats ne sont plus declares : un fait qui ne rend '
            'rien redeviendrait « manquant partout »')
        #: ⚠️ PUBLIABLE : aucune phrase, seulement des empreintes.
        texte = json.dumps(self.ref, ensure_ascii=False)
        self.assertNotIn(
            'sha256:' * 0 + 'ELASTICITE-PRIX', texte,
            'une PHRASE entiere figure dans la reference versionnee : elle '
            'ne doit porter que des empreintes')
        print(f"    MFS-1 reference : {self.ref['nb_faits']} faits, "
              f"assiette declaree en "
              f"{len(self.ref['_assiette_non_couverte'])} caracteres")

    # ── MFS-2 ────────────────────────────────────────────────────────────
    def test_MFS2_le_JEU_n_a_pas_change_depuis_le_figeage(self):
        """⚠️⚠️ *Un ecart lu entre deux assiettes mesurerait les donnees,
        pas le code.* Sans ce controle, changer la graine ferait rougir
        MFS-4 pour une raison qui n'a rien a voir avec la portee."""
        self.assertEqual(
            self.mesure['jeu'], self.ref['jeu'],
            'le jeu du lanceur a change depuis le figeage : la comparaison '
            'de portee mesurerait les DONNEES et non le code. Regenerez la '
            'reference, et justifiez-le.')
        print(f"    MFS-2 jeu identique : {self.ref['jeu']}")

    # ── MFS-3 ────────────────────────────────────────────────────────────
    def test_MFS3_LA_DETTE_EST_PLAFONNEE(self):
        """⚠️⚠️ UN FAIT NEUF A <= 1 SURFACE MORD. C'est l'exigence qui
        empeche la dette de grossir pendant qu'on la regarde."""
        dette = M._dette(self.mesure['faits'])
        self.assertLessEqual(
            dette, M.PLAFOND_DETTE,
            f'la DETTE de publication a AUGMENTE : {dette} faits '
            f"n'atteignent au plus qu'une seule surface, pour un plafond de "
            f'{M.PLAFOND_DETTE}. Un fait calcule qui n atteint aucun '
            f'document signe n existe pas pour qui signe.')
        print(f'    MFS-3 dette {dette} <= plafond {M.PLAFOND_DETTE}')

    # ── MFS-4 ────────────────────────────────────────────────────────────
    def test_MFS4_AUCUNE_PORTEE_NE_SE_DEGRADE(self):
        """⚠️⚠️ L'EXIGENCE QU'UN CONTROLE STATIQUE NE PEUT PAS PORTER.

        Une portee se degrade sans qu'aucun producteur change : il suffit
        qu'un service cesse de lire une cle. Seule une REMESURE le voit.
        """
        degrades = []
        for chemin, attendu in self.ref['faits'].items():
            vu = self.faits.get(chemin)
            if vu is None:
                continue                      # MFS-5 s'en occupe
            if vu['portee'] < attendu['portee']:
                perdues = sorted(set(attendu['surfaces'])
                                 - set(vu['surfaces']))
                degrades.append(
                    f"{chemin} : {attendu['portee']} -> {vu['portee']} "
                    f"(perd {perdues})")
        self.assertEqual(
            degrades, [],
            'la PORTEE de ces faits a BAISSE : une surface signee a cesse '
            'de les publier.\n  ' + '\n  '.join(degrades))
        print(f"    MFS-4 {len(self.ref['faits'])} faits remesures, "
              f'0 portee degradee')

    # ── MFS-5 ────────────────────────────────────────────────────────────
    def test_MFS5_aucun_fait_de_la_reference_n_a_DISPARU_en_silence(self):
        """⚠️ Un fait qui disparait du releve n'est pas rien : ou il a ete
        retire, ou son texte a change. Les deux se declarent."""
        disparus = sorted(set(self.ref['faits']) - set(self.faits))
        self.assertEqual(
            disparus, [],
            f'{len(disparus)} fait(s) de la reference ne sont plus produits '
            f'par la chaine : {disparus[:10]}. Un fait retire se declare, '
            f'et la reference se regenere avec sa justification.')
        #: ⚠️ ET LE SECOND SENS : un chemin conserve dont le TEXTE a change
        #: est un fait REECRIT, pas un fait deplace. On le DIT.
        reecrits = [c for c, a in self.ref['faits'].items()
                    if c in self.faits
                    and self.faits[c]['empreinte'] != a['empreinte']]
        print(f'    MFS-5 0 fait disparu ; {len(reecrits)} fait(s) dont le '
              f'TEXTE a change depuis le figeage')

    # ── MFS-6 ────────────────────────────────────────────────────────────
    def test_MFS6_le_plafond_ne_se_releve_pas_en_silence(self):
        """⚠️⚠️ IL VIT EN DEUX ENDROITS, ET LES DEUX DOIVENT CONCORDER.

        Relever le plafond dans le code sans regenerer la reference le
        ferait passer inapercu ; l'inverse aussi. *Un plafond qu'on peut
        relever d'une main n'est pas un plafond.*
        """
        self.assertEqual(
            self.ref['plafond_dette'], M.PLAFOND_DETTE,
            f"le plafond de la reference ({self.ref['plafond_dette']}) et "
            f'celui du code ({M.PLAFOND_DETTE}) divergent : l un des deux a '
            f'ete change seul')
        self.assertLessEqual(
            self.ref['dette_au_figeage'], self.ref['plafond_dette'],
            'la reference a ete figee sur une dette qui depassait deja son '
            'plafond')
        print(f'    MFS-6 plafond {M.PLAFOND_DETTE} identique au code et a '
              f'la reference')

    # ── MFS-7 ────────────────────────────────────────────────────────────
    def test_MFS7_TEMOIN_l_assiette_n_est_pas_vide(self):
        """⚠️⚠️ SANS CE TEMOIN, UN RELEVE QUI NE TROUVE RIEN PASSE VERT.

        Trois choses doivent rester vraies, sinon ce module atteste du
        vide : des faits, des surfaces, et une exclusion qui retranche
        encore quelque chose.
        """
        self.assertGreater(
            len(self.mesure['faits']), 40,
            f"seulement {len(self.mesure['faits'])} fait(s) releve(s) : "
            f"l'assiette s'est effondree, ce module n'atteste plus rien")
        self.assertGreater(
            len(self.mesure['surfaces_reelles']), 10,
            f"seulement {len(self.mesure['surfaces_reelles'])} surface(s) "
            f'reelle(s) : toute portee serait mecaniquement nulle')
        self.assertGreater(
            self.mesure['hors_perimetre'], 0,
            "l'exclusion des producteurs hors perimetre ne retranche PLUS "
            'RIEN : ou la chaine a change, ou elle a ete oubliee en place')
        self.assertEqual(
            sorted(self.mesure['producteurs']), sorted(M.PRODUCTEURS),
            'les producteurs mesures ont change sans que la reference bouge')
        print(f"    MFS-7 TEMOIN : {len(self.mesure['faits'])} faits, "
              f"{len(self.mesure['surfaces_reelles'])} surfaces, "
              f"{self.mesure['hors_perimetre']} phrase(s) ecartee(s)")

    # ── LE RELEVE, PUBLIE ────────────────────────────────────────────────
    def test_MFS8_RELEVE_la_dette_est_PUBLIEE_agent_par_agent(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE. *Une dette
        qu'on ne voit pas est une dette qu'on ne rembourse pas.*"""
        par_agent: dict[str, list[int]] = {}
        for f in self.mesure['faits']:
            agent = f['chemin'].split('.')[0].split('[')[0]
            case = par_agent.setdefault(agent, [0, 0, 0])
            case[2] += 1
            if f['portee'] == 0:
                case[0] += 1
            elif f['portee'] == 1:
                case[1] += 1
        for agent in sorted(par_agent):
            zero, une, total = par_agent[agent]
            print(f'    MFS-8 {agent} : {total:3} faits, {zero:3} a ZERO '
                  f'surface, {une:3} a UNE seule')
        self.assertTrue(par_agent, 'aucun agent releve')


if __name__ == '__main__':
    unittest.main(verbosity=2)
