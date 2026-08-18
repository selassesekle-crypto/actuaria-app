# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses.py  —  Niveau 2 : Validation des hypothèses H1/H2
# =============================================================================
#
#  ⚠️ CE MODULE NE CALCULE PLUS AUCUN φ — ET N'EN CALCULERA PLUS JAMAIS.
#  ──────────────────────────────────────────────────────────────────
#  L'ancienne H4 « homoscédasticité » vivait ici et produisait un second facteur
#  de sur-dispersion, concurrent de celui du Bootstrap ODP. Elle a été supprimée,
#  pas déplacée, pour trois défauts mesurés :
#
#  · Elle ne mesurait pas ce qu'elle nommait. Son « φ » était la moyenne des
#    variances pondérées des FACTEURS DE DÉVELOPPEMENT ; le φ du Bootstrap est
#    la sur-dispersion des RÉSIDUS DE PEARSON des incréments. Deux grandeurs
#    sans rapport, dans des unités différentes — écart mesuré de 662× sur RAA à
#    843 268× sur GenIns. Exactement la pathologie des deux loss ratios, en pire.
#  · Elle criait au loup sur TOUS les triangles de référence. CV des variances
#    2,12 · 2,40 · 1,31, tous au-dessus de son seuil de 1,0 : elle publiait
#    « Bootstrap ODP non fiable » sur GenIns, RAA et Recours indifféremment.
#  · Elle ne gatait rien. Son `ok` était affiché par douze sites et lu par aucune
#    décision : ni les percentiles, ni le Best Estimate, ni le SCR n'en
#    dépendaient. Une alerte réglementaire sans conséquence est un bruit.
#
#  L'hypothèse d'homogénéité de φ est réelle — England & Verrall (2002) supposent
#  UN φ pour tout le triangle — et elle est désormais testée là où le φ existe :
#  BOOT-H3 dans `n2_hypotheses_bootstrap`, sur les résidus du Bootstrap lui-même,
#  par corrélation de rang calibrée sur nulle paramétrique. Il n'y a plus qu'UN
#  SEUL φ dans le système, celui du Bootstrap, et un verrou de test interdit à ce
#  module d'en publier un second.
#
#  ⚠️ CE MODULE NE CALCULE PLUS AUCUN LOSS RATIO.
#  ─────────────────────────────────────────────
#  L'ancienne H3 « qualité de l'a priori BF » vivait ici et produisait un second
#  loss ratio, concurrent de celui de N3. Trois défauts mesurés l'ont fait
#  supprimer, pas déplacer :
#
#  · Elle divisait `C[i, dernière colonne connue]` par la prime — donc le PAYÉ À
#    DATE, pas l'ultime, contre la figure 14 du guide de l'Institut des Actuaires
#    qui rapporte la CHARGE ULTIME à la prime acquise. Biais systématiquement
#    baissier : −9,08 % sur GenIns, −4,39 % sur RAA.
#  · Son score valait `100 − CV×200`, c'est-à-dire la seule dispersion. Le
#    contrôle de plage était calculé dans `ok`… que la sélection ne lisait jamais.
#    Mesuré : un loss ratio de 364,7 % obtenait 81/100 et passait la gate.
#  · Sans primes, elle fabriquait un loss ratio par `C[i,0] / 0.30` — jumeau du
#    proxy `/0.35` supprimé de N3 au lot précédent, avec une constante inventée
#    DIFFÉRENTE. Sur GenIns, il publiait « LR = 398,9 % » dans le rapport pendant
#    que Bornhuetter-Ferguson y annonçait « non calculée ».
#
#  Le loss ratio a désormais UN SEUL propriétaire, N3, et c'est celui-là que
#  BFCC-H4 juge (`n2_hypotheses_bfcc`). `scores_confiance` disparaît avec lui :
#  après le lot B il n'alimentait plus que BF et Cape Cod, depuis cette seule H3.
#
#  Corrections v5.0 vs v4.0 :
#    · Bug methode_cl_retenue corrigé : valider() expose maintenant
#      'methode_cl_retenue' directement dans le dict retourné,
#      calculée via _choisir_variante_cl() cohérente avec methode_recommandee
#    · Seuils H2 dynamiques depuis lob_config (plus de 15% codé en dur)
#    · _choisir_variante_cl() séparée et documentée (5 cas + fallback)
#
#  Références :
#    · Mack (1993) — ASTIN Bulletin 23(2) : hypothèses H1-H3
#    · Spearman (1904) : test de rang pour H1
#
# =============================================================================

import logging
from typing import Dict, Any, List, Tuple

import numpy as np

from .config.lob_config import get_lob_config
# Reconstruction des facteurs individuels : SOURCE UNIQUE. Les boucles
# identiques qui vivaient ici (H1, H2) ont été remplacées par cet appel.
from .n2_hypotheses_clm import NON_TESTABLE, facteurs_individuels

logger = logging.getLogger('actuaria.a7')


class HypothesesValidator:
    """
    Valide les hypothèses actuarielles AVANT tout calcul de méthode.

    H1 — Corrélation entre facteurs de développement consécutifs
         Test de Spearman sur les facteurs individuels entre colonnes
         consécutives. Si corrélation significative → CL et Mack biaisés.
         ⚠️ NE TESTE PAS l'indépendance des années de survenance, contrairement
         à ce que son ancien libellé affirmait : une corrélation entre facteurs
         de colonnes voisines ne dit rien d'un effet propre à une année de
         survenance ou à une année calendaire. Ce contrôle-là est CLM-H1
         (`n2_hypotheses_clm`), qui applique le test des signes par diagonale
         de l'annexe 9.d du guide IA 2023.

    H2 — Stabilité des facteurs dans le temps
         CV des facteurs par colonne et dérive temporelle (anciens vs récents).
         Seuils paramétrés par LoB (depuis lob_config).

    L'homoscédasticité du Bootstrap ODP N'EST PLUS ICI : elle est devenue
    BOOT-H3 (`n2_hypotheses_bootstrap`), qui l'évalue sur les résidus du
    Bootstrap au lieu des facteurs de développement. Cf. en-tête du module.

    Correction critique v5.0
    ------------------------
    La méthode valider() retourne maintenant 'methode_cl_retenue' dans son
    dict, calculée par _choisir_variante_cl(). Cela garantit la cohérence
    entre la recommandation N2 et le choix de variante CL en N3/N4.
    """

    def __init__(self):
        pass

    # =========================================================================
    #  POINT D'ENTRÉE UNIQUE
    # =========================================================================

    def valider(
        self,
        C:         np.ndarray,
        lob:       str = 'generique',
    ) -> Dict[str, Any]:
        """
        Lance les tests H1 et H2 et retourne un rapport structuré.

        Parameters
        ----------
        C : np.ndarray
            Triangle cumulé (n × m).
        lob : str
            Ligne d'activité — pilote les seuils H2 depuis lob_config.
            Défaut : 'generique' (seuils standards CV=15%, dérive=20%).

        Les paramètres `primes` et `lr_manuel` ont disparu : ils ne servaient
        qu'à l'ancienne H3, qui calculait ici un second loss ratio concurrent de
        celui de N3 (cf. en-tête du module). N2 n'a plus besoin de l'exposition.

        Returns
        -------
        dict avec :
            h1_independance, h2_stabilite
            methode_recommandee     : str  — méthode principale conseillée
            methode_cl_retenue      : str  — variante CL à utiliser en N3
                                      ('standard'|'mediane'|'trimmed_mean'|
                                       'volume_weighted')
            raison_recommandation   : str
            raison_cl               : str  — justification du choix CL
            statut_global           : 'VERT'|'AMBRE'|'ROUGE'
            alertes, infos          : list[str]
        """
        n, m    = C.shape
        alertes: List[str] = []
        infos:   List[str] = []

        # Récupérer la config LoB (seuils H2 adaptés)
        cfg_lob = get_lob_config(lob)

        # ── H1 : Indépendance ────────────────────────────────────────────────
        h1 = self._tester_h1_independance(C, alertes, infos, cfg_lob)

        # ── H2 : Stabilité (seuils depuis lob_config) ────────────────────────
        h2 = self._tester_h2_stabilite(C, alertes, infos, cfg_lob)

        # ── Méthode recommandée ───────────────────────────────────────────────
        methode_rec, raison_rec = self._recommander_methode(h1, h2, n)

        # ── Variante CL : RECOMMANDÉE, plus imposée (lot B) ────────────────────
        # La réserve se calcule désormais sur l'estimateur STANDARD par défaut —
        # celui pour lequel les hypothèses sont testées (CLM) et pour lequel la
        # volatilité de Mack est définie. La recommandation reste calculée et
        # exposée ; l'activer est une décision d'actuaire, via `methode_cl`.
        variante_recommandee, raison_cl = self._choisir_variante_cl(h1, h2)
        methode_cl = 'standard'

        # ── Alertes spécifiques à la LoB ──────────────────────────────────────
        # Ce qui DISTINGUE la LoB retenue d'une voisine presque homonyme, quand
        # elle en a une. `accidents_corporels` et `dommage_corporel_individuel`
        # partagent la LoB Solvabilité II et le σ, mais pas le régime de queue :
        # se tromper change le facteur de queue, donc l'ultime, et rien ne le
        # disait. La configuration le sait — l'actuaire doit le lire.
        if cfg_lob.get('distinction'):
            infos.append(f"ℹ️ [{cfg_lob['label']}] LoB retenue : "
                         f"{cfg_lob['distinction']}")

        for alerte_lob in cfg_lob.get('alertes_specifiques', []):
            infos.append(f"ℹ️ [{cfg_lob['label']}] {alerte_lob}")

        # ── Statut global ─────────────────────────────────────────────────────
        if not h1['ok'] and not h2['ok']:
            statut = 'ROUGE'
        elif not h1['ok'] or not h2['ok']:
            statut = 'AMBRE'
        else:
            statut = 'VERT'

        if self.verbose_log:
            logger.info(
                f"N2 — statut={statut} | methode_rec={methode_rec} | "
                f"methode_cl={methode_cl}"
            )

        return {
            'h1_independance':       h1,
            'h2_stabilite':          h2,
            'methode_recommandee':   methode_rec,
            # Toujours 'standard' sauf choix explicite de l'actuaire en amont :
            # la réserve se calcule sur l'estimateur de Mack (cf. lot B).
            'methode_cl_retenue':      methode_cl,
            # La bascule que le système AURAIT faite automatiquement avant le
            # lot B — exposée pour que l'actuaire puisse la retenir en connaissance
            # de cause, jamais appliquée d'office.
            'variante_cl_recommandee': variante_recommandee,
            'raison_recommandation': raison_rec,
            'raison_cl':             raison_cl,
            'statut_global':         statut,
            'alertes':               alertes,
            'infos':                 infos,
            'lob':                   lob,
            'lob_label':             cfg_lob['label'],
        }

    @property
    def verbose_log(self) -> bool:
        """Log niveau INFO si logger actuaria.a7 actif."""
        return logger.isEnabledFor(logging.INFO)

    # =========================================================================
    #  H1 : CORRÉLATION ENTRE FACTEURS DE DÉVELOPPEMENT CONSÉCUTIFS
    # =========================================================================

    def _tester_h1_independance(
        self,
        C:        np.ndarray,
        alertes:  List,
        infos:    List,
        cfg_lob:  Dict,
    ) -> Dict:
        """
        Corrélation entre facteurs de développement consécutifs.

        Principe : pour chaque paire de colonnes consécutives (j, j+1),
        calculer la corrélation de Spearman entre les vecteurs de facteurs
        individuels f[i,j] = C[i,j+1]/C[i,j].

        ⚠️ CE QUE CE TEST NE FAIT PAS. Il s'intitulait « indépendance des années
        de survenance » et affirmait qu'une corrélation révélait « des années de
        survenance au comportement systématiquement différent » : c'est faux. Une
        corrélation entre facteurs de colonnes voisines mesure la dépendance
        sérielle du DÉVELOPPEMENT, pas un effet propre à une année. Le contrôle
        d'indépendance des années — test des signes par diagonale de l'annexe 9.d
        du guide IA 2023 — est CLM-H1, dans `n2_hypotheses_clm`.

        Le nom de la clé de sortie (`h1_independance`) est conservé : il est lu
        par n4 et les livrables, et le renommer déborderait du périmètre.

        Seuil d'alerte : |corr_moy| > h1_seuil_corr (depuis lob_config).
        H1 rejetée si : corr_moy > seuil ET au moins 2 colonnes significatives
                        (pval < 0.05 et |corr| > seuil).
        """
        try:
            from scipy.stats import spearmanr
        except ImportError:
            # ⚠️ PREMIER DES DEUX CHEMINS QUI RENDENT `ok: True` SUR ZÉRO PAIRE.
            # `statut` est la MOITIÉ MANQUANTE DU LOT F3, qui l'avait donnée à
            # `_h2` seulement : cinq badges de trois livrables se déduisaient
            # encore de `ok`, et affichaient « ✓ VALIDÉE · Score 70/100 » —
            # en vert — au-dessus du texte « H1 non testable ».
            return {
                'ok': True, 'score': 70,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'statut': NON_TESTABLE,
                'message': "H1 non testable — scipy non disponible",
                'details': [],
            }

        n, m     = C.shape
        seuil    = cfg_lob.get('h1_seuil_corr', 0.50)
        corrs    = []
        details  = []

        # Facteurs reconstruits par la SOURCE UNIQUE (n2_hypotheses_clm), plus
        # par une boucle locale : cf. `facteurs_individuels`.
        colonnes = facteurs_individuels(C)

        for j in range(m - 2):
            # Appariement sur l'année i : une paire n'existe que si les trois
            # cellules C[i,j], C[i,j+1], C[i,j+2] sont exploitables — c'est
            # exactement l'intersection des deux colonnes de facteurs.
            suivants = {i: f for i, f, _ in colonnes[j + 1]}
            f_j  = [f for i, f, _ in colonnes[j] if i in suivants]
            f_j1 = [suivants[i] for i, _, _ in colonnes[j] if i in suivants]

            if len(f_j) >= 4:
                corr, pval = spearmanr(f_j, f_j1)
                if not np.isnan(corr):
                    corrs.append(abs(corr))
                    details.append({
                        'colonnes':    f"j={j}→j+1={j+1}",
                        'corr':        round(float(corr), 3),
                        'pval':        round(float(pval), 3),
                        'n_obs':       len(f_j),
                        'significatif': pval < 0.05 and abs(corr) > seuil,
                    })

        if not corrs:
            # ⚠️ SECOND CHEMIN, ET LE PLUS FRÉQUENT : il se déclenche sur tout
            # triangle de moins de 7 années. `_h1` exige DEUX colonnes
            # consécutives à 4 facteurs appariés.
            #
            # ⚠️ `seuil_utilise` RESTE ABSENT ICI, ET C'EST DÉLIBÉRÉ. Le
            # rétablir est « F3b pour H1 » — une autre clé, pour un autre
            # consommateur (le tableau de corrélations de l'Excel, qui retombe
            # sur le seuil GÉNÉRIQUE 0,50). Nommé, non ouvert : ce lot ferme
            # les badges, rien d'autre.
            return {
                'ok': True, 'score': 80,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'statut': NON_TESTABLE,
                'message': "H1 non testable — trop peu de données (< 4 obs par colonne)",
                'details': [],
            }

        corr_moy = float(np.mean(corrs))
        corr_max = float(np.max(corrs))
        n_sig    = sum(1 for d in details if d['significatif'])

        ok    = corr_moy < seuil and n_sig <= 2
        score = max(0, int((1 - corr_moy) * 100))

        # ⚠️ CE TEST NE MESURE PAS L'INDÉPENDANCE DES ANNÉES DE SURVENANCE, ET LE
        # MODULE LE SAVAIT DÉJÀ (cf. l'avertissement de la docstring plus haut :
        # « c'est faux »). Il corrèle les facteurs de COLONNES CONSÉCUTIVES —
        # c'est le test de corrélation de Mack 1994, pas son test d'effet
        # calendaire. L'indépendance des années de survenance est l'objet de
        # CLM-H1, publié DANS LE MÊME RAPPORT sous un intitulé quasi identique.
        # Le rapport affirmait donc, sur ce test-ci, une conclusion qui ne lui
        # appartient pas, à trois lignes d'un verdict qui pouvait la contredire.
        #
        # ⚠️ L'INTITULÉ DE SECTION N'EST PAS TOUCHÉ ICI. « H1 — INDÉPENDANCE
        # (Mack 1993) » reste vague sans être faux — Mack porte bien un test de
        # corrélation. Savoir si ce cadre doit garder ce nom, ou sortir de la
        # chaîne publiée, est une question de fond OUVERTE (constat A7 du
        # relevé B1) : elle se tranche avec sa mesure d'impact, pas ici.
        if not ok:
            alertes.append(
                f"⚠️ H1 Indépendance : corrélation Spearman moyenne = {corr_moy:.2f} "
                f"(seuil LoB = {seuil:.2f}), {n_sig} colonne(s) significative(s). "
                f"Facteurs de colonnes consécutives corrélés → l'a priori exogène "
                f"de BF ou Cape Cod réduit la dépendance au seul triangle."
            )
            message = (
                f"H1 REJETÉE — corrélation Spearman moy={corr_moy:.2f}, "
                f"max={corr_max:.2f}. {n_sig} paire(s) de colonnes montrent "
                f"une dépendance significative. CL et Mack potentiellement biaisés."
            )
        else:
            if corr_moy > seuil * 0.6:
                alertes.append(
                    f"🟡 H1 Indépendance : corrélation moy={corr_moy:.2f} "
                    f"— proche du seuil ({seuil:.2f}), surveiller."
                )
            infos.append(f"✅ H1 Indépendance validée (corr_moy={corr_moy:.2f})")
            # ⚠️ TIENT SOUS 200 CARACTÈRES — `n5_excel` et `n5_rapport` tronquent.
            # Verrouillé par test.
            message = (
                f"H1 VALIDÉE — corrélation Spearman moy={corr_moy:.2f} < {seuil:.2f}. "
                f"Les facteurs de colonnes consécutives ne sont pas corrélés. Ce "
                f"test ne porte pas sur l'indépendance des années de survenance "
                f"(voir CLM-H1)."
            )

        return {
            'ok':                   ok,
            'score':                score,
            'corr_max':             round(corr_max, 3),
            'corr_moy':             round(corr_moy, 3),
            'n_colonnes_testees':   len(corrs),
            'n_colonnes_sig':       n_sig,
            'seuil_utilise':        seuil,
            # ⚠️ MÊME VOCABULAIRE QUE `_h2` DEPUIS F3 : le statut PUBLIÉ se
            # distingue du booléen de GATING. `ok` continue d'alimenter N4 et
            # la sélection des méthodes ; `statut` est ce que les livrables
            # affichent. Les deux coïncident ici, et seulement ici.
            'statut':               'VALIDÉE' if ok else 'REJETÉE',
            'message':              message,
            'details':              details[:5],
        }

    # =========================================================================
    #  H2 : STABILITÉ DES FACTEURS DANS LE TEMPS
    # =========================================================================

    def _tester_h2_stabilite(
        self,
        C:       np.ndarray,
        alertes: List,
        infos:   List,
        cfg_lob: Dict,
    ) -> Dict:
        """
        Stabilité des facteurs de développement dans le temps.

        Deux sous-tests :

        Test 2a — CV des facteurs par colonne
            Pour chaque colonne j, calculer le coefficient de variation
            CV_j = σ(f[·,j]) / μ(f[·,j]).
            Si CV_moy > seuil_cv (depuis lob_config) → instabilité.

        Test 2b — Dérive temporelle
            Pour chaque colonne j, comparer la moyenne des facteurs sur
            la première moitié des années (anciennes) vs la deuxième
            moitié (récentes).
            Si |f_recent - f_ancien| / f_ancien > seuil_derive → dérive.

        Note : seuils paramétrés par LoB (plus stricts en MRH, plus larges
        en RC Médicale) — cf. config/lob_config.py.
        """
        n, m         = C.shape
        seuil_cv     = cfg_lob.get('h2_seuil_cv',     0.15)
        seuil_derive = cfg_lob.get('h2_seuil_derive',  0.20)
        cv_cols      = []
        derive_cols  = []
        details      = []

        colonnes = facteurs_individuels(C)          # source unique

        for j in range(m - 1):
            facteurs = [f for _, f, _ in colonnes[j]]

            if len(facteurs) >= 3:
                arr = np.array(facteurs)
                moy = float(np.mean(arr))
                std = float(np.std(arr, ddof=1))
                cv  = std / moy if moy > 0 else 0.0
                cv_cols.append(cv)

                derive = 0.0
                mid    = len(facteurs) // 2
                if mid >= 2:
                    m_anc   = float(np.mean(arr[:mid]))
                    m_rec   = float(np.mean(arr[mid:]))
                    derive  = abs(m_rec - m_anc) / max(m_anc, 1e-9)
                    derive_cols.append(derive)

                details.append({
                    'colonne': j,
                    'n_obs':   len(facteurs),
                    'f_moyen': round(moy, 4),
                    'cv':      round(cv,  3),
                    'derive':  round(derive, 3),
                })

        if not cv_cols:
            # ⚠️ AUCUNE COLONNE TESTÉE, ET QUATRE LIVRABLES LISAIENT CES ZÉROS
            # COMME DES MESURES. Prouvé par exécution sur un triangle 3×3 sain :
            # le commentaire signé publiait « H2 — STABILITÉ DES FACTEURS :
            # VALIDÉE [score 80/100] », « CV 0,0 % », « dérive 0,0 % » et le
            # constat « les années récentes se développent de la même façon que
            # les années anciennes » — sur ZÉRO colonne. Trois lignes plus bas,
            # BFCC-H2 et BOOT-H2 écrivaient NON TESTABLE sur le même triangle :
            # le rapport se contredisait dans un seul paragraphe.
            #
            # ⚠️ LE VERDICT NE BOUGE PAS, ET C'EST DÉLIBÉRÉ. `ok`, `score`,
            # `ok_cv`, `ok_derive`, `cv_moy`, `derive_moy` gardent EXACTEMENT
            # leurs valeurs : ils alimentent `_choisir_methode`,
            # `_choisir_variante_cl` et N4. Ce lot corrige ce qui est ÉCRIT, pas
            # ce qui est décidé — même arbitrage qu'au lot A1 pour H1. Qu'un
            # `ok: True` par défaut soit tenable sur zéro test reste une question
            # ouverte, à instruire avec sa mesure d'impact.
            #
            # Ce qui est AJOUTÉ est ce qui manquait pour ne plus se tromper :
            # un `statut` distinct du booléen de gating, le compte de colonnes
            # testées, le fait que la dérive n'a pas été calculée, et les seuils
            # DE LA BRANCHE — absents jusqu'ici, ce qui faisait publier 15 % et
            # 20 % (les valeurs génériques) pour les 10 LoB sur 15 qui ont
            # d'autres seuils.
            return {
                'ok': True, 'score': 80,
                'cv_moy': 0, 'cv_max': 0, 'derive_moy': 0,
                'ok_cv': True, 'ok_derive': True,
                'statut':             NON_TESTABLE,
                'n_colonnes_testees': 0,
                'derive_calculee':    False,
                'seuil_cv':           seuil_cv,
                'seuil_derive':       seuil_derive,
                # ⚠️ TIENT SOUS 200 CARACTÈRES, ET C'EST UNE CONTRAINTE MESURÉE :
                # `n5_excel` et `n5_rapport` tronquent le message à 200. Un motif
                # coupé en deux publierait une phrase sans son « pas des
                # mesures ». Verrouillé par test.
                'message': ("H2 NON TESTABLE — aucune période ne porte 3 "
                            "facteurs ou plus. Ni le CV ni la dérive n'ont été "
                            "calculés : les zéros publiés sont des valeurs par "
                            "défaut, pas des mesures."),
                'details': [],
            }

        cv_moy     = float(np.mean(cv_cols))
        cv_max     = float(np.max(cv_cols))
        # ⚠️ UNE DÉRIVE NON CALCULÉE VAUT 0,0 ET SE LIT « AUCUNE DÉRIVE ». Elle
        # n'est mesurée que sur les colonnes portant au moins 4 facteurs
        # (`mid >= 2` ci-dessus) : sur un triangle court, `derive_cols` reste
        # vide, `derive_moy` vaut 0,0 et `ok_derive` devient True PAR
        # CONSTRUCTION. Le chemin est ordinaire, pas un repli.
        derive_calculee = bool(derive_cols)
        derive_moy = float(np.mean(derive_cols)) if derive_cols else 0.0

        ok_cv     = cv_moy    < seuil_cv
        ok_derive = derive_moy < seuil_derive
        ok        = ok_cv and ok_derive

        score = max(0, int((1 - cv_moy / max(seuil_cv * 2, 0.30)) * 100))

        if not ok_cv:
            alertes.append(
                f"⚠️ H2 Stabilité : CV moyen des facteurs = {cv_moy:.1%} "
                f"(seuil {cfg_lob['label']} = {seuil_cv:.0%}) "
                f"→ facteurs instables. Variante médiane ou trimmed_mean recommandée."
            )
        if not ok_derive:
            # ⚠️ LA PRESCRIPTION EST RETIRÉE, PAS REMPLACÉE. Elle disait
            # « Variante volume_weighted recommandée » sur une prémisse
            # MESURÉE FAUSSE (cf. `_choisir_variante_cl`). Quelle variante
            # convient à un triangle en dérive n'est pas tranché : le dire
            # vaut mieux que conseiller sans fondement.
            alertes.append(
                f"⚠️ H2 Dérive temporelle : {derive_moy:.1%} entre facteurs "
                f"anciens et récents (seuil = {seuil_derive:.0%}) "
                f"→ triangle en évolution. Le choix de la variante Chain Ladder "
                f"appartient à l'actuaire : aucune n'est établie pour ce motif."
            )
        # ⚠️ NE JAMAIS ANNONCER UNE DÉRIVE SOUS SON SEUIL SI ELLE N'A PAS ÉTÉ
        # CALCULÉE. Ces deux formulations sont la seule source du texte publié.
        txt_derive = (
            f"dérive={derive_moy:.1%} (seuil {seuil_derive:.0%})"
            if derive_calculee else
            "dérive NON CALCULÉE (aucune période ne porte 4 facteurs, minimum "
            "pour comparer années anciennes et récentes)"
        )
        if ok:
            infos.append(
                f"✅ H2 Stabilité validée — CV={cv_moy:.1%} < {seuil_cv:.0%}, "
                + (f"dérive={derive_moy:.1%} < {seuil_derive:.0%}"
                   if derive_calculee else "dérive non calculée")
            )

        if not ok:
            conclusion = ("Les facteurs montrent une instabilité ou une dérive "
                          "temporelle.")
        elif derive_calculee:
            conclusion = "Les facteurs sont stables dans le temps."
        else:
            # ⚠️ « STABLE DANS LE TEMPS » EST UN CONSTAT SUR LE PORTEFEUILLE. Il
            # ne se publie pas quand la comparaison ancien/récent n'a pas eu lieu.
            conclusion = ("La dispersion des facteurs est acceptable ; leur "
                          "stabilité DANS LE TEMPS n'a pas été testée.")

        message = (
            f"H2 {'VALIDÉE' if ok else 'REJETÉE'} — "
            f"CV moy={cv_moy:.1%} (seuil {seuil_cv:.0%}), "
            f"{txt_derive}. " + conclusion
        )

        return {
            'ok':          ok,
            'ok_cv':       ok_cv,
            'ok_derive':   ok_derive,
            'score':       score,
            'cv_moy':      round(cv_moy,     4),
            'cv_max':      round(cv_max,     4),
            'derive_moy':  round(derive_moy, 4),
            'seuil_cv':    seuil_cv,
            'seuil_derive': seuil_derive,
            'statut':             'VALIDÉE' if ok else 'REJETÉE',
            'n_colonnes_testees': len(cv_cols),
            'derive_calculee':    derive_calculee,
            'message':     message,
            'details':     details,
        }

    # =========================================================================
    #  MÉTHODE RECOMMANDÉE
    # =========================================================================

    def _recommander_methode(
        self,
        h1:      Dict,
        h2:      Dict,
        n:       int,
    ) -> Tuple[str, str]:
        """
        Recommande la méthode principale avec justification explicite.

        ⚠️ PUREMENT INFORMATIF DEPUIS LE LOT B. Cette recommandation ne force
        plus l'inclusion d'une méthode dans le Best Estimate et ne lui accorde
        plus de poids minimum : la sélection se décide sur la couverture du
        motif, année par année, et les méthodes admises sont pondérées à égalité.
        Elle reste affichée comme un avis de lecture du triangle.

        Règles de décision (par ordre de priorité) :
        1. Triangle trop petit (n < 5) → Cape Cod
        2. H1 + H2 validées → Chain Ladder
        3. H1 rejetée → Bornhuetter-Ferguson
        4. H2 rejetée seule → Bornhuetter-Ferguson
        5. Fallback → Chain Ladder (INATTEIGNABLE par construction : R2-R4
           couvrent toutes les combinaisons H1×H2)

        LES DEUX ANCIENNES RÈGLES « H1 rejetée » SONT FUSIONNÉES. Elles
        arbitraient entre Bornhuetter-Ferguson et Cape Cod sur le score de
        l'ancienne H3, supprimée avec le loss ratio de N2. Reconstruire cet
        arbitrage ici est impossible ET indésirable : impossible parce que le
        loss ratio n'existe qu'après N3, indésirable parce que ce qui départage
        réellement les deux méthodes — la provenance de l'a priori et la
        stabilité du loss ratio — est désormais l'objet de BFCC-H4 et BFCC-H5,
        avec un verdict motivé plutôt qu'un score. La recommandation dit donc ce
        qu'elle sait : l'a priori exogène vaut mieux ici que le seul triangle.

        La règle 2 arbitrait auparavant entre « Mack 1993 » et Chain Ladder sur
        un score de méthode. Deux raisons de ne plus le faire : ce score a
        disparu (il reposait sur les anciennes H1/H2/H4), et surtout le point
        estimate de Mack EST celui de Chain Ladder — les présenter comme deux
        recommandations distinctes n'avait pas de sens.
        """
        # Règle 1 : trop peu de données
        if n < 5:
            return 'cape_cod', (
                f"Triangle de petite taille ({n} années) — Cape Cod recommandé : "
                f"il exploite un a priori externe quand les données sont rares."
            )

        # Règle 2 : H1 + H2 validées
        if h1['ok'] and h2['ok']:
            return 'chain_ladder', (
                "H1 et H2 validées → Chain Ladder retenu : les facteurs de "
                "développement sont exploitables tels quels. Mack 1993 en fournit "
                "la volatilité, son estimation centrale étant identique."
            )

        # Règle 3 : H1 rejetée
        if not h1['ok']:
            return 'bornhuetter_ferguson', (
                f"H1 REJETÉE (corr_moy={h1['corr_moy']:.2f}) → CL biaisé. "
                f"Bornhuetter-Ferguson recommandé : ancrage sur un a priori "
                f"extérieur aux corrélations du triangle. Sa recevabilité — "
                f"provenance de l'a priori, stabilité du loss ratio — est jugée "
                f"par BFCC-H4 et BFCC-H5, après N3."
            )

        # Règle 4 : H2 rejetée seule
        if not h2['ok']:
            return 'bornhuetter_ferguson', (
                f"H2 REJETÉE (CV={h2['cv_moy']:.1%}, dérive={h2['derive_moy']:.1%}) "
                f"→ facteurs instables, CL sensible aux outliers. "
                f"Bornhuetter-Ferguson recommandé pour sa robustesse."
            )

        # Règle 5 : fallback terminal — INATTEIGNABLE par construction. R2-R4
        # couvrent toutes les combinaisons H1×H2 (H1∧H2→R2 ; ¬H1→R3 ; ¬H2→R4).
        # Défaut SÛR = chain_ladder (jamais 'bootstrap_odp' via max(scores), que N4
        # ne sait pas pondérer dans le BE).
        return 'chain_ladder', (
            "Fallback sécurisé (inatteignable par construction) — Chain Ladder par défaut."
        )

    # =========================================================================
    #  VARIANTE CL RETENUE (CORRECTION BUG v4.0)
    # =========================================================================

    def _choisir_variante_cl(
        self,
        h1:  Dict,
        h2:  Dict,
    ) -> Tuple[str, str]:
        """
        Choisit la variante de Chain Ladder à utiliser en N3.

        CORRECTION DU BUG v4.0
        ----------------------
        En v4.0, cette logique était dupliquée dans AgentA7Provisionnement
        sous le nom _choisir_methode_cl(), et n'utilisait pas les résultats
        de N2 correctement (la clé 'methode_cl_retenue' n'était jamais
        présente dans le dict retourné par valider()).

        En v5.0 : calculé ici, exposé dans le dict retourné par valider(),
        utilisé directement dans agent.py. Source unique de vérité.

        ⚠️ CETTE FONCTION NE DÉCIDE PLUS — ELLE RECOMMANDE.
        --------------------------------------------------
        Jusqu'au lot B, sa sortie pilotait directement le calcul de la réserve :
        un CV élevé faisait basculer TOUTES les colonnes sur un autre estimateur,
        automatiquement et en silence. Trois raisons de ne plus le faire :

        · Le déclencheur est un SYMPTÔME, pas un diagnostic. Mesuré sur le
          triangle RAA : `cv_moy` = 31,5 % vient d'UNE colonne à 150 %, elle-même
          due à UNE cellule (C[1,0] = 106 contre 1 000-5 700 ailleurs) qui produit
          un facteur de 40,4 face à une médiane de 4,26. La bonne réponse est
          d'examiner ce point, pas de changer d'estimateur partout.
        · Le remède était GLOBAL pour un problème LOCAL : la bascule touchait
          aussi les colonnes à CV de 5 %, où l'estimateur de Mack est optimal.
        · Elle rompait EN SILENCE le lien avec la théorie : σ, la MSEP et les
          percentiles de Mack sont dérivés POUR l'estimateur pondéré volume.
          Conséquence mesurée : l'oracle RAA d'A7 valait 54 059 / 27 022, quand
          Mack et le guide publient 52 135 / 26 909.

        Désormais la recommandation est EXPOSÉE (`variante_cl_recommandee`), et
        le choix appartient à l'actuaire via le paramètre `methode_cl` de run(),
        informé par le diagnostic CLM colonne par colonne.

        Variantes disponibles
        ---------------------
        'standard'        : facteur pondéré volume — estimateur de Mack (1993).
                            f_j = Σ C[i,j+1] / Σ C[i,j]
        'volume_weighted' : ⚠️ PAS un alias de standard, contrairement à ce que
                            cette docstring affirmait. Il pondère par √C[i,j] et
                            non par C[i,j]. Mesuré sur RAA : f₀ = 4,347 contre
                            2,999, réserve 63 500 contre 52 135, soit +22 %.
        'mediane'         : médiane des facteurs individuels par colonne.
                            Robuste aux outliers, insensible au volume.
                            Préféré si CV > seuil élevé.
        'trimmed_mean'    : moyenne écrêtée (10% haut, 10% bas) par colonne.
                            Compromis entre standard et médiane.
                            Préféré si CV modéré (10–20%).

        Règles de décision (5 cas + fallback)
        --------------------------------------
        Cas 1 : H1 + H2 OK                         → standard
        Cas 2 : H2 rejetée sur dérive > 20%         → volume_weighted
        Cas 3 : H2 rejetée sur CV > 20%             → mediane
        Cas 4 : H2 rejetée sur CV 10–20%            → trimmed_mean
        Cas 5 : H1 rejetée seule (H2 OK)            → volume_weighted
        Fallback                                     → standard
        """
        h1_ok    = h1.get('ok', True)
        h2_ok    = h2.get('ok', True)
        cv       = h2.get('cv_moy',    0.0)
        derive   = h2.get('derive_moy', 0.0)
        seuil_cv = h2.get('seuil_cv',   0.15)

        # Cas 1 : tout validé
        if h1_ok and h2_ok:
            return 'standard', (
                "H1 et H2 validées → variante standard (pondération volume). "
                "Estimateur optimal de Mack (1993)."
            )

        # Cas 2 : dérive temporelle dominante
        #
        # ⚠️⚠️ LA JUSTIFICATION PUBLIÉE ICI ÉTAIT FAUSSE SUR TROIS POINTS, ET
        # ELLE ATTEIGNAIT LE RAPPORT SIGNÉ via `raison_cl`. Elle disait
        # « volume_weighted pondère par C[i,j] → favorise les années récentes ».
        # Or `chain_ladder.calculer_facteurs` pondère par √C[i,j] — c'est
        # `standard` qui pondère par C[i,j] — et son propre commentaire dit
        # « donne moins de poids aux très grandes années ».
        #
        # MESURÉ, sur un portefeuille en croissance où l'année récente porte le
        # plus gros volume ET le facteur le plus élevé (1,6000) :
        #       standard         f0 = 1,5808   <- le PLUS proche de 1,6000
        #       volume_weighted  f0 = 1,5674   <- le plus LOIN
        # `volume_weighted` donne donc MOINS de poids aux années récentes que
        # `standard`, dans le cas même que le texte invoquait.
        #
        # ⚠️ LA VALEUR RENDUE NE BOUGE PAS. Inverser la recommandation sur cette
        # seule mesure serait de la conception actuarielle, pas une correction
        # de texte : quelle variante convient à un triangle en DÉRIVE reste
        # OUVERT, et se tranchera avec sa propre mesure. Ce lot retire un
        # conseil sans fondement ; il n'en met pas un autre à la place.
        if not h2_ok and derive > 0.20 and cv <= 0.20:
            return 'volume_weighted', (
                f"H2 rejetée sur dérive temporelle ({derive:.1%} > 20%) : les "
                f"facteurs anciens et récents diffèrent. ⚠️ AUCUNE VARIANTE DE "
                f"CHAIN LADDER N'EST ÉTABLIE POUR CE MOTIF — la justification "
                f"publiée jusqu'ici (« volume_weighted favorise les années "
                f"récentes ») était fausse : il pondère par la RACINE de C[i,j] "
                f"et donne donc MOINS de poids aux gros volumes que "
                f"l'estimateur standard. Le choix appartient à l'actuaire, via "
                f"le paramètre `methode_cl` de run()."
            )

        # Cas 3 : forte dispersion
        if not h2_ok and cv > 0.20:
            return 'mediane', (
                f"H2 rejetée sur forte dispersion (CV={cv:.1%} > 20%). "
                f"Médiane : insensible aux facteurs extrêmes, "
                f"robuste sur portefeuilles hétérogènes."
            )

        # Cas 4 : dispersion modérée
        if not h2_ok and cv > seuil_cv:
            return 'trimmed_mean', (
                f"H2 rejetée sur dispersion modérée (CV={cv:.1%}, "
                f"seuil LoB={seuil_cv:.0%}). "
                f"trimmed_mean écrête les 10% extrêmes sans aller jusqu'à la médiane."
            )

        # Cas 5 : H1 rejetée seule
        # ⚠️ Même retrait qu'au cas 2 : « volume_weighted pour le CL utilisé en
        # entrée de BF » ne reposait sur rien. La valeur rendue est inchangée.
        if not h1_ok:
            return 'volume_weighted', (
                f"H1 rejetée (corr={h1.get('corr_moy', 0):.2f}) — "
                f"BF/Cape Cod seront les méthodes principales (N4). "
                f"Le choix de la variante Chain Ladder servant d'entrée à BF "
                f"appartient à l'actuaire : aucune n'est établie pour ce motif."
            )

        # Fallback sécurisé
        logger.warning(
            f"_choisir_variante_cl : cas non couvert "
            f"(h1={h1_ok}, h2={h2_ok}, cv={cv:.2f}, derive={derive:.2f}) "
            f"→ fallback standard"
        )
        return 'standard', "Fallback sécurisé — standard appliqué par défaut."
