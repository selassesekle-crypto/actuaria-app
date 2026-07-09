# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses.py  —  Niveau 2 : Validation des hypothèses H1/H2/H3/H4
# =============================================================================
#
#  Corrections v5.0 vs v4.0 :
#    · Bug methode_cl_retenue corrigé : valider() expose maintenant
#      'methode_cl_retenue' directement dans le dict retourné,
#      calculée via _choisir_variante_cl() cohérente avec methode_recommandee
#    · Seuils H2 dynamiques depuis lob_config (plus de 15% codé en dur)
#    · H3 proxy documenté explicitement comme approximation sans primes
#    · _choisir_variante_cl() séparée et documentée (5 cas + fallback)
#
#  Références :
#    · Mack (1993) — ASTIN Bulletin 23(2) : hypothèses H1-H3
#    · England & Verrall (2002) : H4 homoscédasticité Bootstrap ODP
#    · Spearman (1904) : test de rang pour H1
#
# =============================================================================

import logging
import math
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from .config.lob_config import get_lob_config

logger = logging.getLogger('actuaria.a7')


class HypothesesValidator:
    """
    Valide les 4 hypothèses actuarielles AVANT tout calcul de méthode.

    H1 — Indépendance des années de survenance (Mack 1993)
         Test de Spearman sur les facteurs individuels entre colonnes
         consécutives. Si corrélation significative → CL et Mack biaisés.

    H2 — Stabilité des facteurs dans le temps
         CV des facteurs par colonne et dérive temporelle (anciens vs récents).
         Seuils paramétrés par LoB (depuis lob_config).

    H3 — Qualité de l'a priori BF
         Cohérence du Loss Ratio a priori avec les années matures du triangle.
         Si pas de primes : estimation proxy documentée comme approximation.

    H4 — Homoscédasticité (England & Verrall 2002)
         Variance des résidus pondérés homogène entre colonnes.
         Condition nécessaire pour la validité du Bootstrap ODP.

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
        primes:    Optional[np.ndarray] = None,
        lob:       str = 'generique',
        lr_manuel: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Lance tous les tests H1-H4 et retourne un rapport structuré.

        Parameters
        ----------
        C : np.ndarray
            Triangle cumulé (n × m).
        primes : np.ndarray, optional
            Vecteur des primes acquises par année de survenance.
        lob : str
            Ligne d'activité — pilote les seuils H2 depuis lob_config.
            Défaut : 'generique' (seuils standards CV=15%, dérive=20%).

        Returns
        -------
        dict avec :
            h1_independance, h2_stabilite, h3_apriori_bf, h4_homosc_bootstrap
            scores_confiance        : dict score 0-100 par méthode
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

        # ── H3 : A priori BF ─────────────────────────────────────────────────
        h3 = self._tester_h3_apriori(C, primes, alertes, infos, cfg_lob, lr_manuel=lr_manuel)

        # ── H4 : Homoscédasticité ─────────────────────────────────────────────
        h4 = self._tester_h4_homosc(C, alertes, infos)

        # ── Scores de confiance par méthode ───────────────────────────────────
        scores = self._calculer_scores(h1, h2, h3, h4, n)

        # ── Méthode recommandée ───────────────────────────────────────────────
        methode_rec, raison_rec = self._recommander_methode(
            scores, h1, h2, h3, n, cfg_lob
        )

        # ── Variante CL retenue (CORRECTION BUG v4.0) ─────────────────────────
        # En v4.0, 'methode_cl_retenue' était absent du dict retourné,
        # forçant agent.py à recalculer via _choisir_methode_cl() avec une
        # logique différente → incohérence silencieuse N2/N4.
        # En v5.0 : calculé ici, exposé dans le dict, utilisé directement en N3.
        methode_cl, raison_cl = self._choisir_variante_cl(h1, h2, n)

        # ── Alertes spécifiques à la LoB ──────────────────────────────────────
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
                f"methode_cl={methode_cl} | scores={scores}"
            )

        return {
            'h1_independance':       h1,
            'h2_stabilite':          h2,
            'h3_apriori_bf':         h3,
            'h4_homosc_bootstrap':   h4,
            'scores_confiance':      scores,
            'methode_recommandee':   methode_rec,
            'methode_cl_retenue':    methode_cl,    # ← CORRECTION BUG v4.0
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
    #  H1 : INDÉPENDANCE DES ANNÉES DE SURVENANCE
    # =========================================================================

    def _tester_h1_independance(
        self,
        C:        np.ndarray,
        alertes:  List,
        infos:    List,
        cfg_lob:  Dict,
    ) -> Dict:
        """
        Test de Mack (1993) — indépendance des années de survenance.

        Principe : pour chaque paire de colonnes consécutives (j, j+1),
        calculer la corrélation de Spearman entre les vecteurs de facteurs
        individuels f[i,j] = C[i,j+1]/C[i,j].

        Si les facteurs d'une colonne sont corrélés avec ceux de la suivante,
        cela signifie que certaines années de survenance ont un comportement
        systématiquement différent — hypothèse d'indépendance de Mack violée.

        Seuil d'alerte : |corr_moy| > h1_seuil_corr (depuis lob_config).
        H1 rejetée si : corr_moy > seuil ET au moins 2 colonnes significatives
                        (pval < 0.05 et |corr| > seuil).
        """
        try:
            from scipy.stats import spearmanr
        except ImportError:
            return {
                'ok': True, 'score': 70,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'message': "H1 non testable — scipy non disponible",
                'details': [],
            }

        n, m     = C.shape
        seuil    = cfg_lob.get('h1_seuil_corr', 0.50)
        corrs    = []
        details  = []

        for j in range(m - 2):
            f_j, f_j1 = [], []
            for i in range(n):
                if j + 2 >= m:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                cij2 = float(C[i, j+2])
                if (cij > 0 and cij1 > 0 and cij2 > 0
                        and not math.isnan(cij) and not math.isnan(cij1)
                        and not math.isnan(cij2)):
                    f_j.append(cij1 / cij)
                    f_j1.append(cij2 / cij1)

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
            return {
                'ok': True, 'score': 80,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'message': "H1 non testable — trop peu de données (< 4 obs par colonne)",
                'details': [],
            }

        corr_moy = float(np.mean(corrs))
        corr_max = float(np.max(corrs))
        n_sig    = sum(1 for d in details if d['significatif'])

        ok    = corr_moy < seuil and n_sig <= 2
        score = max(0, int((1 - corr_moy) * 100))

        if not ok:
            alertes.append(
                f"⚠️ H1 Indépendance : corrélation Spearman moyenne = {corr_moy:.2f} "
                f"(seuil LoB = {seuil:.2f}), {n_sig} colonne(s) significative(s). "
                f"Années de survenance dépendantes → BF ou Cape Cod recommandés."
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
            message = (
                f"H1 VALIDÉE — corrélation Spearman moy={corr_moy:.2f} < {seuil:.2f}. "
                f"Les années de survenance sont indépendantes. CL est approprié."
            )

        return {
            'ok':                   ok,
            'score':                score,
            'corr_max':             round(corr_max, 3),
            'corr_moy':             round(corr_moy, 3),
            'n_colonnes_testees':   len(corrs),
            'n_colonnes_sig':       n_sig,
            'seuil_utilise':        seuil,
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

        for j in range(m - 1):
            facteurs = []
            for i in range(n):
                if j + 1 >= m:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                if (cij > 0 and cij1 > 0
                        and not math.isnan(cij)
                        and not math.isnan(cij1)):
                    facteurs.append(cij1 / cij)

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
            return {
                'ok': True, 'score': 80,
                'cv_moy': 0, 'cv_max': 0, 'derive_moy': 0,
                'ok_cv': True, 'ok_derive': True,
                'message': "H2 non testable — trop peu de données",
                'details': [],
            }

        cv_moy     = float(np.mean(cv_cols))
        cv_max     = float(np.max(cv_cols))
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
            alertes.append(
                f"⚠️ H2 Dérive temporelle : {derive_moy:.1%} entre facteurs "
                f"anciens et récents (seuil = {seuil_derive:.0%}) "
                f"→ triangle en évolution. Variante volume_weighted recommandée."
            )
        if ok:
            infos.append(
                f"✅ H2 Stabilité validée — CV={cv_moy:.1%} < {seuil_cv:.0%}, "
                f"dérive={derive_moy:.1%} < {seuil_derive:.0%}"
            )

        message = (
            f"H2 {'VALIDÉE' if ok else 'REJETÉE'} — "
            f"CV moy={cv_moy:.1%} (seuil {seuil_cv:.0%}), "
            f"dérive={derive_moy:.1%} (seuil {seuil_derive:.0%}). "
            + (
                "Les facteurs sont stables dans le temps."
                if ok else
                "Les facteurs montrent une instabilité ou une dérive temporelle."
            )
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
            'message':     message,
            'details':     details,
        }

    # =========================================================================
    #  H3 : QUALITÉ DE L'A PRIORI BF
    # =========================================================================

    def _tester_h3_apriori(
        self,
        C:         np.ndarray,
        primes:    Optional[np.ndarray],
        alertes:   List,
        infos:     List,
        cfg_lob:   Dict,
        lr_manuel: Optional[float] = None,
    ) -> Dict:
        """
        Qualité de l'a priori Bornhuetter-Ferguson.

        Avec primes fournies (recommandé)
        ----------------------------------
        LR_i = C[i, last_j] / primes[i]  sur les années les plus matures.
        Vérifier : 0.30 < LR_moy < 1.50 et CV_LR < 25%.

        Sans primes (proxy)
        -------------------
        LR_proxy = C[i, last_j] / (C[i, 0] / 0.30)
        ⚠️ APPROXIMATION : suppose que le ratio primes/sinistres initiaux = 0.30.
        Cette hypothèse est fragile — valeur de référence FFA Non-Vie.
        À utiliser uniquement pour orienter le calcul, jamais pour le bilan S2.

        LR de référence marché (depuis lob_config) utilisé pour validation.
        """
        n, m       = C.shape
        nb_matures = min(5, n // 2) if n >= 6 else min(3, n - 1)
        # Cas 0 : LR manuel prioritaire sur proxy et primes
        if lr_manuel is not None and lr_manuel > 0:
            ok    = 0.20 < lr_manuel < 2.0
            score = 85 if ok else 40
            msg   = (
                f"H3 A priori : LR fourni manuellement = {lr_manuel:.1%} "
                f"({'dans' if ok else 'hors'} plage [20%-200%]). "
                f"Source : jugement actuariel - a documenter dans la note methodologique S2."
            )
            if not ok:
                alertes.append(f"H3 A priori : LR manuel = {lr_manuel:.1%} hors plage. Verifier la coherence.")
            else:
                infos.append(msg)
            return {
                'ok': ok, 'score': score,
                'lr_apriori': round(lr_manuel, 4),
                'lr_std': 0.0, 'cv_lr': 0.0,
                'source': 'manuel', 'lr_manuel': lr_manuel,
                'message': msg,
            }


        lr_ref     = cfg_lob.get('lr_marche_reference')
        lr_src     = cfg_lob.get('lr_marche_source', '—')

        # ── Cas 1 : primes fournies ───────────────────────────────────────────
        if primes is not None and len(primes) >= nb_matures:
            lr_annees = []
            for i in range(nb_matures):
                p      = float(primes[i])
                last_j = min(n - i - 1, m - 1)
                u      = float(C[i, last_j])
                if p > 0 and u > 0:
                    lr_annees.append(u / p)

            if lr_annees:
                lr_moy = float(np.mean(lr_annees))
                lr_std = float(np.std(lr_annees, ddof=1)) if len(lr_annees) > 1 else 0.0
                cv_lr  = lr_std / max(lr_moy, 1e-9)

                ok_lr  = 0.30 < lr_moy < 1.50
                ok_cv  = cv_lr < 0.25
                ok     = ok_lr and ok_cv
                score  = max(0, min(100, int(100 - cv_lr * 200)))

                # Comparer avec LR de référence marché
                if lr_ref and abs(lr_moy - lr_ref) > 0.20:
                    alertes.append(
                        f"🟡 H3 A priori : LR calculé = {lr_moy:.1%} vs "
                        f"référence marché = {lr_ref:.1%} ({lr_src}). "
                        f"Ecart > 20 pts — vérifier la cohérence."
                    )

                if not ok_lr:
                    alertes.append(
                        f"⚠️ H3 A priori BF : LR = {lr_moy:.1%} hors plage "
                        f"[30%–150%] — vérifier les primes fournies."
                    )
                if not ok_cv:
                    alertes.append(
                        f"🟡 H3 A priori : CV du LR = {cv_lr:.1%} > 25% "
                        f"— a priori hétérogène entre années matures."
                    )

                if ok:
                    infos.append(
                        f"✅ H3 A priori validé — LR={lr_moy:.1%} "
                        f"(CV={cv_lr:.1%}, {nb_matures} années matures)"
                    )

                return {
                    'ok':         ok,
                    'score':      score,
                    'lr_apriori': round(lr_moy, 4),
                    'lr_std':     round(lr_std, 4),
                    'cv_lr':      round(cv_lr,  4),
                    'nb_matures': nb_matures,
                    'source':     'primes_fournies',
                    'lr_reference': lr_ref,
                    'message': (
                        f"H3 {'VALIDÉE' if ok else 'À VÉRIFIER'} — "
                        f"LR a priori = {lr_moy:.1%} "
                        f"(CV={cv_lr:.1%}, {nb_matures} années matures, "
                        f"source : primes_fournies)."
                    ),
                }

        # ── Cas 2 : sans primes — proxy documenté ─────────────────────────────
        # ⚠️ HYPOTHÈSE PROXY : sinistres initiaux ≈ 30% des primes (FFA Non-Vie)
        # Cette hypothèse est documentée et flaggée — ne pas utiliser pour S2.
        lr_proxy_list = []
        for i in range(nb_matures):
            last_j = min(n - i - 1, m - 1)
            c0     = float(C[i, 0])
            cu     = float(C[i, last_j])
            if c0 > 0 and cu > 0:
                # prime_estimee = sinistres_initiaux / 0.30
                # (hypothèse : SR initial ≈ 30%)
                prime_proxy = c0 / 0.30
                lr_proxy_list.append(cu / prime_proxy)

        lr_proxy = float(np.mean(lr_proxy_list)) if lr_proxy_list else 0.75
        ok       = 0.20 < lr_proxy < 2.0
        score    = 60   # score réduit car proxy sans primes

        alertes.append(
            f"ℹ️ H3 A priori : aucune prime fournie — LR estimé par proxy "
            f"(hypothèse : sinistres_initiaux ≈ 30% des primes). "
            f"LR proxy = {lr_proxy:.1%}. "
            f"⚠️ Approximation — fournir les primes pour un a priori fiable."
        )

        if lr_ref:
            infos.append(
                f"Référence marché disponible : {lr_ref:.1%} ({lr_src})"
            )

        return {
            'ok':         ok,
            'score':      score,
            'lr_apriori': round(lr_proxy, 4),
            'lr_std':     0.0,
            'cv_lr':      0.0,
            'nb_matures': nb_matures,
            'source':     'proxy_sans_primes',
            'lr_reference': lr_ref,
            'message': (
                f"H3 ESTIMÉE (proxy sans primes) — "
                f"LR proxy = {lr_proxy:.1%} "
                f"(hypothèse SR initial = 30%). "
                f"⚠️ Approximation — fournir les primes pour valider."
            ),
        }

    # =========================================================================
    #  H4 : HOMOSCÉDASTICITÉ (Bootstrap ODP)
    # =========================================================================

    def _tester_h4_homosc(
        self,
        C:       np.ndarray,
        alertes: List,
        infos:   List,
    ) -> Dict:
        """
        Homoscédasticité des résidus — condition du Bootstrap ODP.

        Référence : England & Verrall (2002), Insurance: Mathematics and Economics.

        Principe : tester si la variance des résidus pondérés est homogène
        entre colonnes. Pour chaque colonne j, calculer la variance pondérée :

            Var_j = Σ_i w_ij × (f_ij - f̄_j)²  /  Σ_i w_ij
            avec w_ij = C[i,j] (pondération volume)

        Si CV(Var_j) < 1.0 : homoscédasticité acceptable.

        Le facteur de sur-dispersion φ est la moyenne de Var_j — il est
        utilisé par le Bootstrap ODP pour calibrer les résidus de Pearson.
        """
        n, m            = C.shape
        var_cols: List  = []

        for j in range(m - 1):
            facteurs, poids = [], []
            for i in range(n):
                if j + 1 >= m:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                if (cij > 0 and cij1 > 0
                        and not math.isnan(cij)
                        and not math.isnan(cij1)):
                    facteurs.append(cij1 / cij)
                    poids.append(cij)

            if len(facteurs) >= 3:
                arr  = np.array(facteurs)
                w    = np.array(poids)
                moy  = np.average(arr, weights=w)
                var  = np.average((arr - moy) ** 2, weights=w)
                var_cols.append(float(var))

        if len(var_cols) < 3:
            return {
                'ok':     True,
                'score':  75,
                'phi':    0.0,
                'cv_var': 0.0,
                'message': "H4 non testable — moins de 3 colonnes disponibles",
            }

        var_arr = np.array(var_cols)
        cv_var  = float(np.std(var_arr) / max(np.mean(var_arr), 1e-12))
        phi     = float(np.mean(var_arr))

        ok    = cv_var < 1.0
        score = max(0, int((1 - cv_var / 2.0) * 100))

        if not ok:
            alertes.append(
                f"🟡 H4 Homoscédasticité : CV variances = {cv_var:.2f} > 1.0 "
                f"→ Bootstrap ODP moins fiable. "
                f"Interpréter les percentiles P90/P99.5 avec prudence."
            )
            message = (
                f"H4 HÉTÉROSCÉDASTICITÉ détectée — CV variances = {cv_var:.2f}. "
                f"La variance des résidus n'est pas stable entre colonnes. "
                f"Bootstrap ODP fournit des intervalles approximatifs."
            )
        else:
            infos.append(f"✅ H4 Homoscédasticité validée (CV var={cv_var:.2f}, φ={phi:.6f})")
            message = (
                f"H4 VALIDÉE — CV variances = {cv_var:.2f} < 1.0, "
                f"φ={phi:.6f}. Bootstrap ODP fiable."
            )

        return {
            'ok':     ok,
            'score':  score,
            'phi':    round(phi,    6),
            'cv_var': round(cv_var, 3),
            'message': message,
        }

    # =========================================================================
    #  SCORES DE CONFIANCE PAR MÉTHODE
    # =========================================================================

    def _calculer_scores(
        self,
        h1: Dict, h2: Dict, h3: Dict, h4: Dict, n: int,
    ) -> Dict[str, int]:
        """
        Score de confiance 0–100 pour chaque méthode actuarielle.
        Basé sur les hypothèses qui la sous-tendent directement.

        Chain Ladder   : dépend de H1 (50%) + H2 (50%)
        Mack 1993      : dépend de H1 (50%) + H2 (30%) + H4 (20%)
        BF             : dépend de H1 (20%) + H2 (20%) + H3 (60%)
        Cape Cod       : dépend de H1 (30%) + H2 (30%) + H3 (40%)
        Bootstrap ODP  : dépend de H1 (30%) + H2 (30%) + H4 (40%)

        Bonus taille : +0.5 par année supplémentaire au-delà de 5 (max +10).
        """
        s1, s2, s3, s4 = h1['score'], h2['score'], h3['score'], h4['score']
        bonus = min(10, (n - 5) * 0.5) if n > 5 else 0

        return {
            'chain_ladder':         int(min(100, s1*0.50 + s2*0.50 + bonus)),
            'mack_1993':            int(min(100, s1*0.50 + s2*0.30 + s4*0.20 + bonus)),
            'bornhuetter_ferguson': int(min(100, s1*0.20 + s2*0.20 + s3*0.60)),
            'cape_cod':             int(min(100, s1*0.30 + s2*0.30 + s3*0.40)),
            'bootstrap_odp':        int(min(100, s1*0.30 + s2*0.30 + s4*0.40)),
        }

    # =========================================================================
    #  MÉTHODE RECOMMANDÉE
    # =========================================================================

    def _recommander_methode(
        self,
        scores:  Dict,
        h1:      Dict,
        h2:      Dict,
        h3:      Dict,
        n:       int,
        cfg_lob: Dict,
    ) -> Tuple[str, str]:
        """
        Recommande la méthode principale avec justification explicite.

        Règles de décision (par ordre de priorité) :
        1. Triangle trop petit (n < 5) → Cape Cod
        2. H1 + H2 validées → Mack 1993 si score ≥ 70, sinon Chain Ladder
        3. H1 rejetée + H3 fiable → Bornhuetter-Ferguson
        4. H1 rejetée + H3 peu fiable → Cape Cod
        5. H2 rejetée seule → Bornhuetter-Ferguson
        6. Fallback → meilleur score

        La config LoB peut surcharger la méthode par défaut via
        'methode_par_defaut' (non obligatoire).
        """
        # Règle 1 : trop peu de données
        if n < 5:
            return 'cape_cod', (
                f"Triangle de petite taille ({n} années) — Cape Cod recommandé : "
                f"il exploite un a priori externe quand les données sont rares."
            )

        # Règle 2 : H1 + H2 validées
        if h1['ok'] and h2['ok']:
            if scores['mack_1993'] >= 70:
                return 'mack_1993', (
                    f"H1 et H2 validées → Mack 1993 retenu : hypothèses satisfaites "                    f"et score de confiance suffisant ({scores['mack_1993']}/100). "                    f"Mack 1993 quantifie l'incertitude S2 sans biais."                )
            return 'chain_ladder', (
                f"H1 et H2 validées → Chain Ladder retenu. "                f"Score Mack = {scores['mack_1993']}/100 < 70 : "                f"triangle insuffisamment développé pour Mack complet, "                f"CL standard plus robuste."            )

        # Règle 3 : H1 rejetée + a priori BF fiable
        if not h1['ok'] and h3['score'] >= 60:
            return 'bornhuetter_ferguson', (
                f"H1 REJETÉE (corr_moy={h1['corr_moy']:.2f}) → CL biaisé. "
                f"Bornhuetter-Ferguson recommandé : ancrage sur a priori indépendant "
                f"des corrélations du triangle "
                f"(score H3 = {h3['score']}/100)."
            )

        # Règle 4 : H1 rejetée + a priori peu fiable
        if not h1['ok'] and h3['score'] < 60:
            return 'cape_cod', (
                f"H1 REJETÉE (corr_moy={h1['corr_moy']:.2f}) et a priori BF peu fiable "
                f"(score H3 = {h3['score']}/100 < 60). "
                f"Cape Cod recommandé : estime le LR directement depuis les données."
            )

        # Règle 5 : H2 rejetée seule
        if not h2['ok']:
            return 'bornhuetter_ferguson', (
                f"H2 REJETÉE (CV={h2['cv_moy']:.1%}, dérive={h2['derive_moy']:.1%}) "
                f"→ facteurs instables, CL sensible aux outliers. "
                f"Bornhuetter-Ferguson recommandé pour sa robustesse."
            )

        # Règle 6 : fallback sur meilleur score
        best = max(scores, key=lambda k: scores[k])
        return best, (
            f"Méthode sélectionnée sur score de confiance maximum : "
            f"{best} = {scores[best]}/100."
        )

    # =========================================================================
    #  VARIANTE CL RETENUE (CORRECTION BUG v4.0)
    # =========================================================================

    def _choisir_variante_cl(
        self,
        h1:  Dict,
        h2:  Dict,
        n:   int,
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

        Variantes disponibles
        ---------------------
        'standard'        : facteur pondéré volume — optimal si H1+H2 validées.
                            f_j = Σ C[i,j+1] / Σ C[i,j]
        'volume_weighted' : identique à standard (alias explicite).
                            Préféré si dérive temporelle ou H1 rejetée seule.
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
        if not h2_ok and derive > 0.20 and cv <= 0.20:
            return 'volume_weighted', (
                f"H2 rejetée sur dérive temporelle ({derive:.1%} > 20%). "
                f"volume_weighted pondère par C[i,j] → favorise les années "
                f"récentes (volumes généralement plus élevés)."
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
        if not h1_ok:
            return 'volume_weighted', (
                f"H1 rejetée (corr={h1.get('corr_moy', 0):.2f}) — "
                f"BF/Cape Cod seront les méthodes principales (N4). "
                f"volume_weighted pour le CL utilisé en entrée de BF."
            )

        # Fallback sécurisé
        logger.warning(
            f"_choisir_variante_cl : cas non couvert "
            f"(h1={h1_ok}, h2={h2_ok}, cv={cv:.2f}, derive={derive:.2f}) "
            f"→ fallback standard"
        )
        return 'standard', "Fallback sécurisé — standard appliqué par défaut."
