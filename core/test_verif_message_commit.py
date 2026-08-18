# =============================================================================
#  LE GARDE-FOU DU MESSAGE DE COMMIT SE VERIFIE LUI-MEME
# =============================================================================
#
#  ⚠️ GATE : `py -m unittest discover -s core -t .`
#
#  ⚠️ POURQUOI CES TESTS EXISTENT. `scripts/verif_message_commit.py` est le
#  bras d'une règle que j'ai enfreinte trois fois en cinq jours. Un contrôle
#  écrit pour rattraper une négligence ne vaut que s'il est lui-même éprouvé :
#  un garde-fou qui laisse passer ce qu'il devait refuser est pire que rien,
#  parce qu'il donne la confiance sans la couverture.
#
#  Trois choses sont vérifiées ici, et ce sont exactement les trois que
#  Selasse a exigées :
#    · il REFUSE la violation plantée — un sujet à 77 caractères ;
#    · il LAISSE PASSER un message conforme ;
#    · il ne bloque AUCUN cas légitime — en particulier les lignes de
#      commentaire que git ajoute lui-même au fichier de message.
#
#  Le module est chargé PAR CHEMIN, comme `scripts/proprete.py` : il n'y a
#  aucun `import verif_message_commit` à trouver dans le dépôt.
# =============================================================================

import importlib.util
import os
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHEMIN = os.path.join(_RACINE, 'scripts', 'verif_message_commit.py')


def _module():
    spec = importlib.util.spec_from_file_location('verif_message_commit',
                                                  _CHEMIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _module()

#: Un message conforme, de la forme réellement employée dans ce dépôt.
_CONFORME = (
    "fix(a7): le Word dit enfin ce qu'il engage\n"
    "\n"
    "Le rendu Word etait garde par une condition qui ne s'executait que\n"
    "si une cle API etait posee. Sans cle, il ne publiait ni origine ni\n"
    "engagement.\n"
    "\n"
    "Gate direction_non_vie : Ran 1121 tests, OK (skipped=3).\n"
)


class G1_Il_Refuse_La_Violation_Plantee(unittest.TestCase):
    """⚠️ SANS CETTE EPREUVE, UN CONTROLE QUI PASSE NE PROUVE RIEN."""

    def test_un_sujet_a_77_caracteres_est_refuse(self):
        # 77 = la violation exacte de 8bc1ddf, a032bd4 et ad9595b.
        sujet = 'fix(a7): ' + 'x' * (77 - len('fix(a7): '))
        self.assertEqual(len(sujet), 77)
        violations = V.verifier(sujet + '\n')
        self.assertTrue(violations, 'un sujet a 77 est passe')
        self.assertIn('sujet', violations[0])
        print('    OK G1-1 le sujet a 77 caracteres est refuse')

    def test_un_sujet_a_76_passe(self):
        # ⚠️ LA BORNE EST INCLUSIVE. Un controle qui refuse 76 refuserait du
        # legitime, et se ferait desactiver au premier lot presse.
        sujet = 'fix(a7): ' + 'x' * (76 - len('fix(a7): '))
        self.assertEqual(len(sujet), 76)
        self.assertEqual(V.verifier(sujet + '\n'), [])
        print('    OK G1-2 la borne 76 est inclusive')

    def test_une_ligne_de_corps_a_77_est_refusee(self):
        msg = 'fix(a7): sujet court\n\n' + 'y' * 77 + '\n'
        violations = V.verifier(msg)
        self.assertTrue(any('77 caracteres' in v for v in violations),
                        f'ligne de corps a 77 non detectee : {violations}')
        print('    OK G1-3 une ligne de corps a 77 est refusee')

    def test_un_caractere_non_ascii_est_refuse(self):
        msg = 'fix(a7): le resume\n\nLa qualite des donnees est verifiee.\n'
        self.assertEqual(V.verifier(msg), [])
        violations = V.verifier(msg.replace('verifiee', 'vérifiée'))
        self.assertTrue(any('non-ASCII' in v for v in violations),
                        f'accent non detecte : {violations}')
        print('    OK G1-4 un caractere non-ASCII est refuse')

    def test_le_sujet_doit_etre_suivi_d_une_ligne_vide(self):
        colle = 'fix(a7): sujet\nune ligne de corps collee au sujet\n'
        self.assertTrue(any('ligne vide' in v for v in V.verifier(colle)))
        print('    OK G1-5 le sujet colle au corps est refuse')


class G2_Il_Laisse_Passer_Le_Legitime(unittest.TestCase):
    """⚠️ UN GARDE-FOU QUI REFUSE DU JUSTE SE FAIT DESACTIVER."""

    def test_un_message_conforme_passe(self):
        self.assertEqual(V.verifier(_CONFORME), [])
        print('    OK G2-1 un message conforme passe')

    def test_les_commentaires_de_git_ne_comptent_pas(self):
        # ⚠️ LE CAS QUI AURAIT FAIT ECHOUER TOUS LES COMMITS. Le hook recoit
        # le fichier BRUT : git y ajoute ses propres lignes `#`, longues et,
        # en locale francaise, accentuees. Les compter refuserait tout.
        parasites = (
            '# Please enter the commit message for your changes. Lines starting\n'
            "# with '#' will be ignored, and an empty message aborts the commit.\n"
            '#\n'
            '# Sur la branche main\n'
            '# Modifications qui seront validees :\n'
            '#\tmodifie :         direction_non_vie/provisionnement/a7.py\n'
        )
        self.assertEqual(V.verifier(_CONFORME + parasites), [])
        print('    OK G2-2 les lignes de commentaire de git sont ignorees')

    def test_le_diff_verbeux_est_ignore(self):
        # `commit.verbose` colle le diff apres la ligne de ciseaux. Il contient
        # du code, donc des lignes longues et des accents : hors message.
        verbeux = (V.CISEAUX + '\n'
                   'diff --git a/x.py b/x.py\n'
                   '+    # une ligne de code tres longue et accentuee : '
                   + 'e' * 90 + ' — développement\n')
        self.assertEqual(V.verifier(_CONFORME + verbeux), [])
        print('    OK G2-3 le diff verbeux est ignore')


class G3_Ce_Qu_Il_Ne_Couvre_Pas(unittest.TestCase):
    """⚠️ CE QUE LE CONTROLE NE VOIT PAS EST ECRIT, PAS SOUS-ENTENDU.

    Un garde-fou dont on croit la couverture plus large qu'elle n'est
    reproduit le defaut qu'il corrige : une etiquette qui affirme plus que
    la chose ne porte.
    """

    def test_il_ne_voit_pas_Co_Authored_By(self):
        # La regle « JAMAIS de Co-Authored-By » est permanente elle aussi,
        # mais elle n'a pas ete demandee ici : Selasse en a nomme trois.
        # Ce test CONSTATE l'absence de couverture, il ne la deplore pas.
        msg = _CONFORME + '\nCo-Authored-By: quelqu un <x@y.z>\n'
        self.assertEqual(V.verifier(msg), [],
                         'la couverture a change : mettre a jour ce test')
        print('    OK G3-1 Co-Authored-By N EST PAS couvert (constate)')

    def test_il_ne_voit_pas_le_contenu(self):
        # Il juge la FORME. Un message conforme mais faux passe — c est le
        # role de la relecture, pas du hook.
        menteur = ('fix(a7): rien de ce qui suit n est vrai\n\n'
                   'Gate : Ran 99999 tests, OK. Aucun euro deplace.\n')
        self.assertEqual(V.verifier(menteur), [])
        print('    OK G3-2 le contenu n est PAS verifie (constate)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
