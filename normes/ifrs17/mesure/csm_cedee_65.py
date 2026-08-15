# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §65, §65A, §68 : LA CSM CÉDÉE À LA COMPTABILISATION
=============================================================================

§65 — « Les dispositions du paragraphe 38 […] sont modifiées pour tenir
compte du fait que, dans le cas d'un groupe de contrats de réassurance
détenus, IL N'Y A PAS DE PROFIT NON ACQUIS et qu'il y a plutôt UN COÛT NET OU
UN PROFIT NET pour l'entité lorsqu'elle acquiert la réassurance. Ainsi, à
moins que le paragraphe 65A s'applique, […] l'entité doit comptabiliser tout
coût net ou profit net […] comme une marge sur services contractuels égale à
la somme : a) des flux de trésorerie d'exécution ; b) du montant
décomptabilisé à cette date de tout actif ou passif précédemment comptabilisé
au titre des flux de trésorerie liés au groupe […] ; c) des flux de trésorerie
survenant à cette date ; et d) de tout produit comptabilisé en résultat net
en application du paragraphe 66A. »

§65A — « Si le coût net de l'achat d'une couverture de réassurance est lié à
des ÉVÉNEMENTS SURVENUS AVANT L'ACHAT du groupe […], l'entité doit,
NONOBSTANT LES DISPOSITIONS DU PARAGRAPHE B5, comptabiliser IMMÉDIATEMENT ce
coût en tant que CHARGE au résultat net. »

§68 — « Les contrats de réassurance détenus NE PEUVENT PAS ÊTRE DÉFICITAIRES.
Par conséquent, les dispositions des paragraphes 47 à 52 ne s'appliquent
pas. »

⚠️⚠️ C'EST LE PREMIER BLOC DE CE CHANTIER OÙ LA NORME CALCULE VRAIMENT. Sur
les paragraphes précédents de la réassurance détenue, la réponse à « que
permet-il de calculer ? » était le plus souvent « rien, c'est une décision
d'entité ». §65 est une SOMME DE QUATRE TERMES, et elle est mécanique.

⚠️⚠️ ET §68 N'EST PAS UNE REMARQUE, C'EST UN INVARIANT QUI CHANGE LE TYPE DU
RÉSULTAT. Parce que §47-52 sont écartés, la CSM d'un groupe CÉDÉ est SIGNÉE :
elle peut valoir un coût net, SANS PLANCHER À ZÉRO et SANS composante de
perte. Celle d'un groupe ÉMIS, elle, est bloquée à zéro et §47-52 fabriquent
une composante de perte à la place. ⚠️ LE MÊME MOT DÉSIGNE DONC DEUX OBJETS
QUI N'ONT PAS LES MÊMES BORNES — un commissaire aux comptes le sondera, et
mieux vaut l'avoir écrit que le lui laisser découvrir. Ce module REFUSE toute
tentative de plancher : `csm_initiale_65` ne rend jamais un zéro qu'elle
n'aurait pas calculé.

⚠️ ET §65 b) EST EXIGÉ DÉCLARÉ, PAS SUPPOSÉ NUL. Le montant décomptabilisé
d'un actif ou passif antérieur n'a aucune source dans les données livrées. Le
supposer nul serait un CHOIX SILENCIEUX, et il n'est pas neutre : il gonfle
la CSM du montant omis. C'est exactement ce que la séparation non fournie a
coûté sur B66 d) — 55 sur l'exemple ICA 5.2 — et la leçon s'applique
verbatim : reçu déclaré, refusé à défaut.

⚠️ §65A EST MIXTE, ET LA FRONTIÈRE COMPTE. Le TRAITEMENT est mécanique — le
coût sort de la CSM et devient une charge immédiate. La QUALIFICATION « lié à
des événements survenus avant l'achat » est une attribution que seule
l'entité peut faire, et le texte la renforce en écartant B5 (« nonobstant »).
Le module reçoit donc la part antérieure DÉCLARÉE, et l'applique mécaniquement.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §65, §65A, §68, §38, §47 à §52, §66A, B5.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_DECOMPTABILISATION_NON_DECLAREE = 'decomptabilisation_65b_non_declaree'
MOTIF_PART_ANTERIEURE_INVALIDE = 'part_anterieure_65a_invalide'
MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE = 'convention_de_signe_non_declaree'

#: ⚠️⚠️ LA CONVENTION DE SIGNE SE DÉCLARE, ELLE NE SE DEVINE PAS. §65 dit
#: qu'il y a « un COÛT NET ou un PROFIT NET pour l'entité », sans fixer de
#: signe : celui-ci dépend de la façon dont l'appelant signe ses flux
#: d'exécution. Or §65A retranche une portion du COÛT — il faut donc savoir
#: quel côté est un coût, et le supposer bâtirait tout le garde-fou sur une
#: convention non établie.
#:
#: ⚠️ ET LES DEUX BRANCHES DONNENT DES RÉSULTATS DIFFÉRENTS, ce qui a été
#: vérifié avant d'écrire ce paramètre : pour une même CSM de −100, l'une
#: voit un coût de 100 et admet un §65A jusqu'à 100, l'autre voit un profit
#: et refuse tout §65A. Un choix dont les branches coïncideraient serait
#: fictif, et ce dépôt en a déjà payé un.
COUT_NET_NEGATIF = 'COUT_NET_NEGATIF'
COUT_NET_POSITIF = 'COUT_NET_POSITIF'
CONVENTIONS = (COUT_NET_NEGATIF, COUT_NET_POSITIF)

#: ⚠️ L'ÉTIQUETTE QUE TOUT LECTEUR DE LA CSM CÉDÉE DOIT AVOIR LUE.
ASYMETRIE_65_68 = (
    "⚠️ CETTE MARGE EST SIGNÉE, ET CELLE D'UN GROUPE ÉMIS NE L'EST PAS. §68 "
    "pose que les contrats de réassurance détenus NE PEUVENT PAS être "
    "déficitaires et écarte les §47 à 52 : un COÛT NET reste une marge sur "
    "services contractuels négative, sans plancher à zéro et sans composante "
    "de perte. Un groupe ÉMIS, lui, est planché à zéro et porte une "
    "composante de perte à la place. Le même mot désigne deux objets qui "
    "n'ont pas les mêmes bornes.")


class CsmCedee(NamedTuple):
    """La CSM cédée à l'origine, ses quatre termes, et ce que §65A en sort."""
    csm:                  float
    charge_immediate_65a: float
    flux_execution:       float
    decomptabilisation:   float
    flux_du_jour:         float
    produit_66a:          float
    convention:           str
    motif:                str

    @property
    def cout_net(self) -> float:
        """Le COÛT NET du §65, en valeur absolue — zéro s'il y a un profit.

        ⚠️ IL SE LIT SOUS LA CONVENTION DÉCLARÉE, jamais sous une convention
        supposée : c'est elle qui dit quel côté est un coût.
        """
        if self.convention == COUT_NET_NEGATIF:
            return -self.csm if self.csm < 0 else 0.0
        return self.csm if self.csm > 0 else 0.0


def csm_initiale_65(*, flux_execution: float,
                    convention_de_signe: str,
                    decomptabilisation_declaree=None,
                    motif_decomptabilisation: str = '',
                    flux_du_jour: float = 0.0,
                    produit_66a: float = 0.0,
                    part_anterieure_65a: float = 0.0) -> CsmCedee:
    """§65 — la somme des quatre termes, §65A retranché, §68 respecté.

    ⚠️ `decomptabilisation_declaree` N'A PAS DE DÉFAUT À ZÉRO, ET C'EST LE
    POINT. Aucune donnée livrée ne porte ce montant ; le supposer nul
    gonflerait la CSM d'autant, silencieusement. Il se déclare — fût-ce à
    zéro — avec le motif qui l'établit.

    ⚠️ ET AUCUN PLANCHER N'EST APPLIQUÉ. §68 écarte les §47-52 : un coût net
    sort négatif, tel qu'il est calculé.
    """
    if convention_de_signe not in CONVENTIONS:
        raise RefusMesure(
            MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE,
            f"la convention de signe n'est pas déclarée (reçu "
            f"{convention_de_signe!r}, attendu l'une de {CONVENTIONS}). §65 "
            f"parle d'« un COÛT NET ou un PROFIT NET pour l'entité » sans "
            f"fixer de signe, et §65A retranche une portion du COÛT : sans "
            f"savoir quel côté est un coût, le contrôle du §65A reposerait "
            f"sur une convention supposée. ⚠️ Les deux branches ne "
            f"coïncident pas — pour une CSM de −100, l'une voit un coût de "
            f"100 et admet un §65A jusqu'à 100, l'autre voit un profit et "
            f"refuse tout §65A")

    if decomptabilisation_declaree is None:
        raise RefusMesure(
            MOTIF_DECOMPTABILISATION_NON_DECLAREE,
            "§65 b) exige « le montant décomptabilisé à cette date de tout "
            "actif ou passif précédemment comptabilisé au titre des flux de "
            "trésorerie liés au groupe » ; il n'est pas déclaré. ⚠️ LE "
            "SUPPOSER NUL SERAIT UN CHOIX SILENCIEUX, et il n'est pas neutre : "
            "il gonfle la marge sur services contractuels du montant omis. "
            "Déclarer zéro est légitime — l'absence de déclaration ne l'est "
            "pas, et la différence entre les deux est tout ce qui sépare un "
            "chiffre établi d'un chiffre supposé")
    if not est_renseigne(motif_decomptabilisation):
        raise RefusMesure(
            MOTIF_DECOMPTABILISATION_NON_DECLAREE,
            f"le montant du §65 b) vaut {decomptabilisation_declaree} mais "
            f"aucun motif ne l'établit (reçu "
            f"{motif_decomptabilisation!r}). Un montant sans sa source est "
            f"invérifiable, et « non vide » n'est pas « renseigné »")
    if part_anterieure_65a < 0:
        raise RefusMesure(
            MOTIF_PART_ANTERIEURE_INVALIDE,
            f"la part rattachée à des événements antérieurs vaut "
            f"{part_anterieure_65a} ; §65A vise un COÛT à comptabiliser en "
            f"charge, donc un montant positif ou nul")

    brut = (flux_execution + float(decomptabilisation_declaree)
            + flux_du_jour + produit_66a)
    provisoire = CsmCedee(brut, 0.0, flux_execution,
                          float(decomptabilisation_declaree), flux_du_jour,
                          produit_66a, convention_de_signe, '')
    cout = provisoire.cout_net

    if part_anterieure_65a:
        if part_anterieure_65a > cout + 1e-9:
            raise RefusMesure(
                MOTIF_PART_ANTERIEURE_INVALIDE,
                f"la part §65A rattachée à des événements antérieurs "
                f"({part_anterieure_65a}) excède le coût net du groupe "
                f"({cout}), lu sous la convention "
                f"« {convention_de_signe} ». §65A retranche une portion du "
                f"COÛT NET de l'achat : elle ne peut pas en excéder le tout, "
                f"et l'admettre créerait un profit à partir d'une charge")
        #: ⚠️ La charge sort de la marge DANS LE SENS DU COÛT, pas dans un
        #: sens fixe : sous l'autre convention, le signe s'inverse.
        sortie = (part_anterieure_65a if convention_de_signe == COUT_NET_NEGATIF
                  else -part_anterieure_65a)
        csm = brut + sortie
    else:
        csm = brut

    return CsmCedee(csm=csm, charge_immediate_65a=part_anterieure_65a,
                    flux_execution=flux_execution,
                    decomptabilisation=float(decomptabilisation_declaree),
                    flux_du_jour=flux_du_jour, produit_66a=produit_66a,
                    convention=convention_de_signe,
                    motif=_motif_65(csm, part_anterieure_65a,
                                    convention_de_signe))


def _motif_65(csm: float, part_65a: float, convention: str) -> str:
    """Ce que la CSM cédée établit, et sous quelle étiquette."""
    cout = (csm < 0) if convention == COUT_NET_NEGATIF else (csm > 0)
    sens = ("COÛT NET pour l'entité" if cout and csm
            else "position exactement nulle" if not csm
            else "PROFIT NET pour l'entité")
    base = (f"§65 : marge sur services contractuels de {csm:,.2f} à la "
            f"comptabilisation initiale, soit un {sens} sous la convention "
            f"« {convention} ». §65 écarte la notion de profit non acquis "
            f"pour la réassurance détenue. ")
    if part_65a:
        base += (
            f"§65A appliqué : {part_65a:,.2f} rattaché à des événements "
            f"survenus AVANT l'achat sort de la marge et devient une charge "
            f"immédiate au résultat net — « nonobstant les dispositions du "
            f"paragraphe B5 ». ⚠️ La QUALIFICATION de cette part appartient à "
            f"l'entité ; ce module l'a reçue déclarée et l'a appliquée. ")
    return base + ASYMETRIE_65_68
