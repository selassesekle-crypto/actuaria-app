"""
sp_style.py — la direction produit ses documents sans dépendre d'une autre.

LE DÉFAUT FERMÉ (D00)
`sp_rapport_sante.py` et `sp_rapport_prevoyance.py` importaient dix noms depuis
`direction_non_vie.provisionnement.a7_provisionnement.n5_rapport`. C'étaient les
**deux seuls imports inter-directions** du périmètre — relevé exhaustif : 478
nœuds d'import, 0 vers Vie/Épargne-Retraite, 0 appel à la frontière LLM.

L'autonomie de CALCUL était donc réelle : les 33 modules démarrent dans un arbre
amputé de Non-Vie. Mais l'autonomie de LIVRABLE ne l'était pas, et le repli
dégradait en silence :

    feuille de style .......  18 774 -> 50 caracteres   (-99,7 %)
    HTML Prevoyance ........  41 728 -> 17 498 car.     (-58,1 %)
    logo ................... SVG integre -> <img src="">
    couleur de rejet ....... var(--rouge) NON DEFINIE

Le dernier point est le plus grave, et il n'est pas cosmétique : **les
hypothèses rejetées perdaient leur couleur de rejet**. La couleur portait une
information, le repli la supprimait, et rien ne le signalait. Le document était
produit, il avait l'air complet, il ne l'était pas.

Et `LOGO_SVG` n'était **pas** redéfini dans le bloc `except` — neuf noms sur
dix l'étaient. Tout appel à ce nom en mode autonome aurait levé `NameError` ;
le défaut était latent, pas actif.

CE QUE CE MODULE FAIT, ET CE QU'IL NE FAIT PAS
Il fournit un repli COMPLET — tous les noms, toutes les variables de couleur
réellement utilisées par les gabarits — et il **déclare son mode** dans le
document au lieu de dégrader sans le dire.

Il ne supprime pas la dépendance : en présence de Non-Vie, la feuille d'origine
est utilisée, à l'identique. Si la vente par licence autonome devient un axe
réel, la bonne cible est de **déplacer la feuille de style dans `core`**, le
socle déjà partagé par les deux directions. C'est un chantier d'architecture
distinct, signalé et non traité ici.

⚠️ Note levée depuis l'audit : `_statut_col` et `_statut_label` — que je
soupçonnais de porter une règle de décision — sont bien PRÉSENTATIONNELS. Le
bloc de repli existant les définit lui-même comme une table de couleurs et une
table de libellés.
"""

__all__ = ["CSS_AUTONOME", "LOGO_SVG_AUTONOME", "charger_style",
           "mention_mode_autonome", "uri_svg"]

# Palette de la direction. Les noms de variables sont ceux qu'emploient les
# gabarits : les redefinir ailleurs ferait perdre la couleur de rejet.
NAVY = "#0B1E3D"
GOLD = "#C9A84C"
BLANC = "#FFFFFF"
ROUGE = "#C0392B"
VERT = "#1E8449"
ORANGE = "#E67E22"
SLATE = "#8A9BB0"

CSS_AUTONOME = """
<style>
:root{
  --navy:#0B1E3D; --gold:#C9A84C; --blanc:#FFFFFF;
  --rouge:#C0392B; --vert:#1E8449; --ambre:#E67E22; --slate:#8A9BB0;
  --encre:#12181F; --encre-2:#4A5662; --fond:#FFFFFF; --fond-2:#F4F6F8;
  --trait:#D5DAE0;
}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--fond);color:var(--encre);
  font-family:Inter,"Segoe UI",Helvetica,Arial,sans-serif;
  font-size:10pt;line-height:1.55}
h1,h2,h3{font-family:Inter,"Segoe UI",Helvetica,Arial,sans-serif;
  color:var(--navy);line-height:1.2;margin:24px 0 10px}
h1{font-size:20pt;border-bottom:3px solid var(--gold);padding-bottom:8px}
h2{font-size:14pt} h3{font-size:11.5pt}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:9pt}
th{background:var(--fond-2);text-align:left;padding:7px 9px;color:var(--encre-2);
  border-bottom:2px solid var(--trait)}
td{padding:6px 9px;border-bottom:1px solid var(--trait)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.statut-vert{color:var(--vert);font-weight:600}
.statut-ambre{color:var(--ambre);font-weight:600}
.statut-rouge{color:var(--rouge);font-weight:600}
.hyp-err .hyp-label{background:rgba(192,57,43,0.10);color:var(--rouge);
  border-right:3px solid var(--rouge)}
.encadre{border-left:4px solid var(--gold);background:var(--fond-2);
  padding:10px 14px;margin:14px 0}
.mention-repli{border:1px solid var(--ambre);background:#FBF3E3;
  color:var(--ambre);padding:8px 12px;margin:0 0 18px;font-size:8.5pt}
img{max-width:100%}
</style>
"""

# Cartouche neutre : il ne porte la marque d'aucune autre direction.
LOGO_SVG_AUTONOME = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 44" width="240" '
    'height="44" role="img" aria-label="Direction Sante-Prevoyance">'
    '<rect x="0" y="0" width="240" height="44" fill="#0B1E3D"/>'
    '<rect x="0" y="38" width="240" height="6" fill="#C9A84C"/>'
    '<text x="14" y="27" fill="#FFFFFF" font-family="Inter,Helvetica,Arial,'
    'sans-serif" font-size="14" letter-spacing="1.6">SANTE-PREVOYANCE</text>'
    "</svg>"
)


def uri_svg(svg):
    """SVG en data-URI, sans dépendance externe."""
    from urllib.parse import quote

    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")


def charger_style():
    """Rend `(css, logo_svg, logo_uri, autonome)`.

    `autonome=True` signale que la direction tourne SANS `direction_non_vie` :
    l'appelant doit alors inscrire la mention dans le document, au lieu de
    dégrader en silence.
    """
    try:
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            LOGO_SVG, LOGO_URI, _css,
        )

        return _css(), LOGO_SVG, LOGO_URI, False
    except ImportError:
        return (CSS_AUTONOME, LOGO_SVG_AUTONOME,
                uri_svg(LOGO_SVG_AUTONOME), True)


def mention_mode_autonome(autonome):
    """Le document DIT dans quel mode il a été produit.

    Chaîne vide en mode nominal : la mention ne doit apparaître que lorsqu'elle
    a quelque chose à dire.
    """
    if not autonome:
        return ""
    return (
        '<p class="mention-repli">Document produit en mode licence autonome '
        "(Direction Sant&eacute;-Pr&eacute;voyance seule). Mise en forme "
        "interne&nbsp;; aucun contenu de calcul n&rsquo;est affect&eacute;.</p>"
    )
