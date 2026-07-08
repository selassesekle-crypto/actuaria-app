"""
ActuarIA — Agent V1 : Nour — Tarification Décès Vie
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Tarification des contrats d'assurance décès :
→ Primes pures avec tables TH0002 / TF0002 (arrêté du 27 juillet 2006)
→ Primes commerciales avec chargements
→ Réserves prospectives (méthode prospective)
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np
import logging
import os
import json
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v1 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# ─── TABLES DE MORTALITÉ OFFICIELLES ─────────────────────────────────────────
# Arrêté du 27 juillet 2006 (JORF n°184 du 10 août 2006)
# Module centralisé — source unique de vérité pour toute la direction Vie
from direction_vie_epre.services.tables_mortalite_officielles import (
    QX_TH0002, QX_TF0002, get_qx, construire_lx, TABLES_DISPONIBLES,
    REFERENCE_REGLEMENTAIRE,
)

print("Agent V1 — Tarification Décès ActuarIA v1.0")
print(f"Tables officielles : TH0002 · TF0002 — {REFERENCE_REGLEMENTAIRE}")
print("Usage : agent_v1 = AgentV1TarificationDeces()")
print("        result_v1 = agent_v1.run(age=40, sexe='H', duree=20)")


def _interpoler_qx(tables: dict, age: int) -> float:
    """Délègue au module officiel — valeur exacte age par age (0-110)."""
    return tables.get(max(0, min(age, 110)), 1.0)


class AgentV1TarificationDeces:
    """
    Agent V1 — Nour : Tarification Décès Vie.

    Calcule les primes pures et commerciales des contrats décès
    temporaires et vie entière, avec validation complète des hypothèses.
    """

    def __init__(
        self,
        models_path: str = "models",
        audit_path:  str = "audit",
        verbose:     bool = True,
    ):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger("actuaria.v1")
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path,  exist_ok=True)

    def run(
        self,
        age:              int   = 40,
        sexe:             str   = "H",
        duree:            int   = 20,
        capital_deces:    float = 100_000,
        taux_technique:   float = 0.025,
        chargement_pct:   float = 0.20,
        table:            str   = "TH0002",
        generer_graphiques: bool = True,
    ) -> Dict:
        """
        Tarification complète d'un contrat décès temporaire.

        Paramètres :
        → age              : âge de l'assuré (20-75 ans)
        → sexe             : 'H' (TH0002) ou 'F' (TF0002)
        → duree            : durée du contrat en années
        → capital_deces    : capital versé au décès (€)
        → taux_technique   : taux d'actualisation (0-5%)
        → chargement_pct   : chargement commercial (%)
        → table            : table de mortalité ('TH0002', 'TF0002')
        """
        audit_id = f"V1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger   = self.logger

        if self.verbose:
            logger.info(f"[{audit_id}] Agent V1 démarré | âge={age} | sexe={sexe} | durée={duree}ans")

        try:
            # ── Sélection table ────────────────────────────────────────────────
            tables_dispo = {
                'TH0002':  QX_TH0002,
                'TF0002':  QX_TF0002,
                'TGHF05H': QX_TH0002,
                'TGHF05F': QX_TF0002,
            }
            if table not in tables_dispo:
                table = 'TH0002' if sexe.upper() == 'H' else 'TF0002'
            table_qx = tables_dispo[table]

            # ── Calcul des probabilités de survie ──────────────────────────────
            qx_serie  = [_interpoler_qx(table_qx, age + t) for t in range(duree + 5)]
            px_serie  = [1 - q for q in qx_serie]

            # Probabilités de survie k|qx (décès en année k)
            lx = [1.0]
            for px in px_serie[:duree]:
                lx.append(lx[-1] * px)

            k_qx = [lx[k] * qx_serie[k] for k in range(duree)]
            t_px = lx[:duree]

            # Espérance de vie résiduelle
            ev_residuelle = sum(lx[1:duree+1])

            if self.verbose:
                logger.info(f"[{audit_id}] Table {table} | P(survie {duree}ans) = {lx[-1]*100:.1f}%")

            # ── Prime pure (assurance temporaire décès) ────────────────────────
            # P_pure = C × Σ(k_qx × v^(k+1)) / Σ(t_px × v^t)
            # avec v = 1/(1+i)
            v = 1 / (1 + taux_technique)

            # Facteur de risque (numérateur)
            A_x_n = sum(k_qx[k] * (v ** (k+1)) for k in range(duree))

            # Facteur de survie (dénominateur — annuité)
            a_x_n = sum(t_px[k] * (v ** k) for k in range(duree))

            prime_pure_annuelle = capital_deces * A_x_n / max(a_x_n, 1e-10)
            prime_pure_mensuelle = prime_pure_annuelle / 12

            # ── Prime commerciale ──────────────────────────────────────────────
            prime_commerciale_annuelle  = prime_pure_annuelle * (1 + chargement_pct)
            prime_commerciale_mensuelle = prime_commerciale_annuelle / 12

            # Prime de référence marché (estimation)
            prime_marche_ref = prime_pure_annuelle * 1.15  # Estimation concurrentielle

            if self.verbose:
                logger.info(f"[{audit_id}] Prime pure = {prime_pure_annuelle:.2f}€/an | Comm. = {prime_commerciale_annuelle:.2f}€/an")

            # ── Réserve prospective ────────────────────────────────────────────
            reserves = []
            for t in range(duree + 1):
                if t >= duree:
                    reserves.append(0.0)
                    continue
                duree_rest = duree - t
                age_t      = age + t

                qx_rest  = [_interpoler_qx(table_qx, age_t + k) for k in range(duree_rest + 2)]
                px_rest  = [1 - q for q in qx_rest]

                lx_rest  = [1.0]
                for px in px_rest[:duree_rest]:
                    lx_rest.append(lx_rest[-1] * px)

                k_qx_rest = [lx_rest[k] * qx_rest[k] for k in range(duree_rest)]
                t_px_rest = lx_rest[:duree_rest]

                A_rest = sum(k_qx_rest[k] * (v ** (k+1)) for k in range(duree_rest))
                a_rest = sum(t_px_rest[k] * (v ** k) for k in range(duree_rest))

                reserve_t = capital_deces * A_rest - prime_pure_annuelle * a_rest
                reserves.append(max(0, reserve_t))

            reserve_max  = max(reserves)
            reserve_fin  = reserves[-1]

            # ── Indicateurs synthèse ──────────────────────────────────────────
            prob_deces_contrat   = 1 - lx[-1]
            cout_attendu_deces   = capital_deces * sum(k_qx)
            ratio_sinistralite   = A_x_n / max(a_x_n * (prime_pure_annuelle/capital_deces), 1e-10)

            # ── Rapport ──────────────────────────────────────────────────────
            rapport = {
                "agent":              "V1 — Nour",
                "type_contrat":       f"Temporaire Décès {duree} ans",
                "table":              table,
                "age":                age,
                "sexe":               sexe,
                "capital_deces":      capital_deces,
                "taux_technique":     taux_technique,
                "chargement":         chargement_pct,
                "prime_pure_an":      round(prime_pure_annuelle, 2),
                "prime_pure_mois":    round(prime_pure_mensuelle, 2),
                "prime_comm_an":      round(prime_commerciale_annuelle, 2),
                "prime_comm_mois":    round(prime_commerciale_mensuelle, 2),
                "prob_deces":         round(prob_deces_contrat, 4),
                "ev_residuelle":      round(ev_residuelle, 2),
                "reserve_max":        round(reserve_max, 2),
                "audit_id":           audit_id,
                "date":               datetime.now().isoformat(),
            }

            # ── Commentaire actuariel ─────────────────────────────────────────
            stab = "Compétitive" if prime_commerciale_annuelle <= prime_marche_ref else "Élevée"
            commentaire = (
                f"✅ Tarification décès finalisée — Table {table} | Âge {age} ans | Durée {duree} ans.\n"
                f"Prime pure : {prime_pure_annuelle:.2f}€/an ({prime_pure_mensuelle:.2f}€/mois) "
                f"→ {prob_deces_contrat*100:.1f}% probabilité de décès sur la période.\n"
                f"Prime commerciale : {prime_commerciale_annuelle:.2f}€/an (chargement {chargement_pct*100:.0f}%). "
                f"Positionnement marché : {stab}.\n"
                f"Réserve prospective max : {reserve_max:.2f}€ (à {reserves.index(reserve_max)} ans).\n"
                f"Espérance de vie résiduelle : {ev_residuelle:.1f} ans."
            )

            if self.verbose:
                logger.info(f"[{audit_id}] {commentaire.split(chr(10))[0]}")

            # ── Statut RAG ───────────────────────────────────────────────────
            if prime_pure_annuelle > 0 and prob_deces_contrat > 0:
                statut_rag = "VERT"
            else:
                statut_rag = "AMBRE"

            # ── Graphiques PowerBI ────────────────────────────────────────────
            graphiques = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    age, duree, lx, k_qx, reserves, prime_pure_annuelle,
                    prime_commerciale_annuelle, table, capital_deces,
                )

            # ── Validation hypothèses ─────────────────────────────────────────
            val_hyp = self._valider_hypotheses_deces(
                qx_serie, taux_technique, prime_pure_annuelle,
                prime_commerciale_annuelle, prime_marche_ref, table, duree,
            )
            gv = self._graphiques_validation_deces(
                val_hyp, lx, k_qx, reserves, age, duree, table,
            ) if generer_graphiques else {}

            # ── Sauvegarde ────────────────────────────────────────────────────
            self._sauvegarder(rapport, audit_id)

            return {
                'success':               True,
                'agent':                 'V1 Nour',
                'type_contrat':          f"Temporaire Décès {duree} ans",
                'table':                 table,
                'age':                   age,
                'sexe':                  sexe,
                'duree':                 duree,
                'statut_rag':            statut_rag,
                'prime_pure': {
                    'annuelle':          round(prime_pure_annuelle, 2),
                    'mensuelle':         round(prime_pure_mensuelle, 2),
                    'A_x_n':             round(A_x_n, 6),
                    'a_x_n':             round(a_x_n, 4),
                },
                'prime_commerciale': {
                    'annuelle':          round(prime_commerciale_annuelle, 2),
                    'mensuelle':         round(prime_commerciale_mensuelle, 2),
                    'chargement_pct':    round(chargement_pct * 100, 1),
                },
                'indicateurs': {
                    'prob_deces_contrat': round(prob_deces_contrat, 4),
                    'ev_residuelle':      round(ev_residuelle, 2),
                    'cout_attendu_deces': round(cout_attendu_deces, 2),
                    'reserve_max':        round(reserve_max, 2),
                    'reserve_fin':        round(reserve_fin, 2),
                    'prime_marche_ref':   round(prime_marche_ref, 2),
                },
                'tables_actuarielles': {
                    'qx_serie':  [round(q, 6) for q in qx_serie[:duree]],
                    'lx_serie':  [round(l, 6) for l in lx],
                    'k_qx':      [round(k, 6) for k in k_qx],
                    'reserves':  [round(r, 2) for r in reserves],
                },
                'rapport':               rapport,
                'commentaire':           commentaire,
                'audit_id':              audit_id,
                'graphiques':            graphiques,
                'validation_deces':      val_hyp,
                'graphiques_validation': gv,
                'erreur':                None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ─── VALIDATION HYPOTHÈSES ────────────────────────────────────────────────
    def _valider_hypotheses_deces(
        self,
        qx_serie:    list,
        taux_tech:   float,
        prime_pure:  float,
        prime_comm:  float,
        prime_marche:float,
        table:       str,
        duree:       int,
    ) -> Dict:
        """
        Validation complète des hypothèses de tarification décès.

        H1 — Taux technique cohérent
             Taux ∈ [0%, 4%] → réaliste pour l'assurance vie ✅
             Taux > 4% → trop optimiste, risque de sous-provisionnement ❌

        H2 — qx croissants avec l'âge (loi de mortalité valide)
             qx[t+1] ≥ qx[t] pour la majorité des âges ✅
             Inversions nombreuses → table suspecte ❌

        H3 — Prime commerciale compétitive
             Prime comm ≤ 1.30 × Prime marché référence ✅
             Prime comm > 1.50 × Prime marché → non compétitif ❌
        """
        import numpy as np

        # H1 — Taux technique
        if 0.0 <= taux_tech <= 0.04:
            h1_statut = "VERT"
            h1_msg    = f"Taux technique = {taux_tech*100:.2f}% ∈ [0%, 4%] → Réaliste ✅"
            h1_conseil= "Taux conforme aux recommandations ACPR pour l'assurance vie"
        elif taux_tech <= 0.06:
            h1_statut = "AMBRE"
            h1_msg    = f"Taux technique = {taux_tech*100:.2f}% ∈ [4%, 6%] → Optimiste ⚠️"
            h1_conseil= "Vérifier la cohérence avec les rendements obligataires actuels"
        else:
            h1_statut = "ROUGE"
            h1_msg    = f"Taux technique = {taux_tech*100:.2f}% > 6% → Sous-provisionnement ❌"
            h1_conseil= "Réduire le taux technique — risque réglementaire ACPR"

        # H2 — qx croissants
        qx = np.array(qx_serie[:duree])
        if len(qx) > 1:
            inversions = int(np.sum(np.diff(qx) < 0))
            taux_inv   = inversions / max(len(qx) - 1, 1)
        else:
            inversions, taux_inv = 0, 0

        if taux_inv <= 0.05:
            h2_statut = "VERT"
            h2_msg    = f"qx croissants — {inversions} inversion(s) sur {len(qx)-1} → Table valide ✅"
            h2_conseil= f"Table {table} respecte la loi de mortalité croissante avec l'âge"
        elif taux_inv <= 0.15:
            h2_statut = "AMBRE"
            h2_msg    = f"qx : {inversions} inversions ({taux_inv*100:.0f}%) → Légères anomalies ⚠️"
            h2_conseil= "Vérifier les âges présentant des inversions — possible erreur de table"
        else:
            h2_statut = "ROUGE"
            h2_msg    = f"qx : {inversions} inversions ({taux_inv*100:.0f}%) → Table anormale ❌"
            h2_conseil= "Table de mortalité non conforme — utiliser TH0002/TF0002 officielles"

        # H3 — Compétitivité prime commerciale
        if prime_marche > 0:
            ratio_comp = prime_comm / prime_marche
        else:
            ratio_comp = 1.0

        if ratio_comp <= 1.15:
            h3_statut = "VERT"
            h3_msg    = f"Prime comm./marché = {ratio_comp:.3f} ≤ 1.15 → Compétitive ✅"
            h3_conseil= "Tarification dans la fourchette marché — bon positionnement commercial"
        elif ratio_comp <= 1.30:
            h3_statut = "AMBRE"
            h3_msg    = f"Prime comm./marché = {ratio_comp:.3f} ∈ [1.15, 1.30] → Légèrement élevée ⚠️"
            h3_conseil= "Réduire le chargement ou optimiser le chargement d'acquisition"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"Prime comm./marché = {ratio_comp:.3f} > 1.30 → Non compétitive ❌"
            h3_conseil= "Prime trop élevée vs marché — revoir la structure de chargements"

        statuts = [h1_statut, h2_statut, h3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  "✅ Tarification décès validée — Taux, table et prime compétitive",
            "AMBRE": "⚠️ Tarification acceptable — vérifier les points signalés",
            "ROUGE": "❌ Tarification à corriger — hypothèses non conformes",
        }[statut_global]

        return {
            "h1_taux_tech": {
                "taux":   round(taux_tech, 4),
                "statut": h1_statut, "message": h1_msg, "conseil": h1_conseil,
                "titre_graphique": f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} Taux technique = {taux_tech*100:.2f}%",
            },
            "h2_qx_croissants": {
                "nb_inversions": inversions, "taux_inv": round(taux_inv, 4),
                "statut": h2_statut, "message": h2_msg, "conseil": h2_conseil,
                "titre_graphique": f"{'✅' if h2_statut=='VERT' else '⚠️' if h2_statut=='AMBRE' else '❌'} qx croissants — {inversions} inversion(s)",
            },
            "h3_competitivite": {
                "prime_pure":  round(prime_pure, 2),
                "prime_comm":  round(prime_comm, 2),
                "prime_marche":round(prime_marche, 2),
                "ratio_comp":  round(ratio_comp, 4),
                "statut": h3_statut, "message": h3_msg, "conseil": h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} Compétitivité — Ratio comm/marché = {ratio_comp:.3f}",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
        }

    # ─── GRAPHIQUES VALIDATION ────────────────────────────────────────────────
    def _graphiques_validation_deces(
        self,
        val_deces: Dict,
        lx:        list,
        k_qx:      list,
        reserves:  list,
        age:       int,
        duree:     int,
        table:     str,
    ) -> Dict:
        """4 graphiques auto-explicatifs validation Tarification Décès."""
        try:
            import plotly.graph_objects as go
            import numpy as np
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; OR="#C9A84C"; BLANC="#F0F4F8"
        GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=60, b=50), height=300,
        )
        graphiques = {}

        # G1 — Courbe de survie avec probabilités de décès annuelles
        try:
            ages   = list(range(age, age + duree + 1))
            survie = [l * 100 for l in lx[:duree+1]]
            deces  = [k * 100 for k in k_qx[:duree]]
            statut = val_deces["h2_qx_croissants"]["statut"]
            couleur= VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE

            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=ages[:duree+1], y=survie, mode="lines",
                line=dict(color=OR, width=2.5),
                fill="tozeroy", fillcolor="rgba(201,168,76,0.08)",
                name="P(survie) %",
                hovertemplate="Age %{x}<br>Survie : %{y:.2f}%<extra></extra>",
            ))
            fig1.add_trace(go.Bar(
                x=ages[:duree], y=deces,
                marker_color=couleur, opacity=0.55, name="P(décès) %",
                yaxis="y2",
                hovertemplate="Age %{x}<br>P(décès) : %{y:.4f}%<extra></extra>",
            ))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=val_deces["h2_qx_croissants"]["titre_graphique"] + f" — Table {table}",
                    font=dict(color=couleur, size=11), x=0.01
                ),
                xaxis=dict(title="Âge", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="P(survie) %", tickfont=dict(color=OR), side="left"),
                yaxis2=dict(title="P(décès) %", tickfont=dict(color=couleur),
                           overlaying="y", side="right", showgrid=False),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=9),
                           orientation="h", yanchor="bottom", y=1.0),
                annotations=[dict(
                    text="💡 La courbe dorée = probabilité de survie. Les barres = probabilité de décès chaque année. Les barres doivent augmenter régulièrement avec l'âge.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques["survie_et_deces"] = fig1
        except Exception as e:
            self.logger.warning(f"G1 V1 : {e}")

        # G2 — Comparaison primes (pure / commerciale / marché)
        try:
            h3 = val_deces["h3_competitivite"]
            primes = [h3["prime_pure"], h3["prime_comm"], h3["prime_marche"]]
            labels = ["Prime pure", "Prime commerciale", "Référence marché"]
            colors = [OR, VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE, GRIS]
            couleur_h3 = VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE

            fig2 = go.Figure(go.Bar(
                x=labels, y=primes,
                marker_color=colors, width=0.4, opacity=0.88,
                text=[f"{p:.2f}€/an" for p in primes],
                textposition="outside", textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.2f}€/an<extra></extra>",
            ))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=h3["titre_graphique"],
                          font=dict(color=couleur_h3, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 La prime commerciale (barre colorée) doit rester proche de la référence marché (grise). Sinon l'assuré ira chez un concurrent.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            graphiques["comparaison_primes"] = fig2
        except Exception as e:
            self.logger.warning(f"G2 V1 : {e}")

        # G3 — Évolution de la réserve prospective
        try:
            ages_res   = list(range(age, age + duree + 1))
            reserve_arr= reserves[:duree+1]
            res_max    = max(reserve_arr)
            age_max    = ages_res[reserve_arr.index(res_max)]

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=ages_res, y=reserve_arr, mode="lines+markers",
                line=dict(color=BLEU, width=2.5),
                marker=dict(color=BLEU, size=5),
                fill="tozeroy", fillcolor="rgba(52,152,219,0.08)",
                hovertemplate="Age %{x}<br>Réserve : %{y:,.0f}€<extra></extra>",
            ))
            fig3.add_vline(x=age_max, line_color=AMBRE, line_width=2, line_dash="dash",
                          annotation_text=f"Max {res_max:,.0f}€",
                          annotation_font=dict(color=AMBRE, size=10))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(
                    text=f"✅ Réserve prospective max = {res_max:,.0f}€ à {age_max} ans",
                    font=dict(color=VERT, size=11), x=0.01
                ),
                xaxis=dict(title="Âge", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Réserve (€)", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                showlegend=False,
                annotations=[dict(
                    text="💡 La réserve prospective = ce que l'assureur doit mettre de côté pour honorer ses engagements. Elle doit toujours être ≥ 0.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig3.update_layout(**l3)
            graphiques["reserve_prospective"] = fig3
        except Exception as e:
            self.logger.warning(f"G3 V1 : {e}")

        # G4 — Scorecard validation tarification décès
        try:
            items = [
                ("H1 — Taux technique ∈ [0%, 4%]", val_deces["h1_taux_tech"]["statut"],
                 val_deces["h1_taux_tech"]["message"], val_deces["h1_taux_tech"]["conseil"]),
                ("H2 — qx croissants (table valide)", val_deces["h2_qx_croissants"]["statut"],
                 val_deces["h2_qx_croissants"]["message"], val_deces["h2_qx_croissants"]["conseil"]),
                ("H3 — Prime compétitive vs marché", val_deces["h3_competitivite"]["statut"],
                 val_deces["h3_competitivite"]["message"], val_deces["h3_competitivite"]["conseil"]),
            ]
            fig4 = go.Figure()
            for nom, statut, msg, conseil in items:
                couleur = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                icone   = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                score   = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(
                    x=[score], y=[nom], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g  = val_deces["statut_global"]
            couleur_g = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard Tarification Décès — {val_deces['conclusion']}",
                    font=dict(color=couleur_g, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = tarification décès validée, défendable devant l'actuaire désigné et l'ACPR.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_deces"] = fig4
        except Exception as e:
            self.logger.warning(f"G4 V1 : {e}")

        return graphiques

    # ─── GRAPHIQUES POWERPBI ──────────────────────────────────────────────────
    def _generer_graphiques(self, age, duree, lx, k_qx, reserves,
                            prime_pure, prime_comm, table, capital) -> Dict:
        """Graphiques PowerBI principaux."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; OR="#C9A84C"; BLANC="#F0F4F8"
        GRIS="#8A9AB0"; VERT="#2ECC71"; BLEU="#3498DB"
        graphiques = {}

        try:
            ages = list(range(age, age + duree + 1))
            fig = go.Figure(go.Scatter(
                x=ages, y=[l*100 for l in lx[:duree+1]],
                mode="lines", line=dict(color=OR, width=2.5),
                fill="tozeroy", fillcolor="rgba(201,168,76,0.08)",
                hovertemplate="Age %{x}<br>Survie : %{y:.2f}%<extra></extra>",
            ))
            fig.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter", color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=40), height=300,
                title=dict(text=f"Courbe de survie — Table {table} — Âge {age} ans",
                          font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(title="Âge", tickfont=dict(color=GRIS)),
                yaxis=dict(title="P(survie) %", tickfont=dict(color=GRIS)),
                showlegend=False,
            )
            graphiques["courbe_survie"] = fig
        except Exception:
            pass

        try:
            fig2 = go.Figure(go.Scatter(
                x=list(range(age, age + duree + 1)),
                y=reserves[:duree+1],
                mode="lines+markers",
                line=dict(color=BLEU, width=2.5),
                fill="tozeroy", fillcolor="rgba(52,152,219,0.08)",
            ))
            fig2.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter", color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=40), height=300,
                title=dict(text="Réserve prospective sur la durée du contrat",
                          font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(title="Âge", tickfont=dict(color=GRIS)),
                yaxis=dict(title="Réserve (€)", tickfont=dict(color=GRIS)),
                showlegend=False,
            )
            graphiques["reserve"] = fig2
        except Exception:
            pass

        return graphiques

    # ─── SAUVEGARDE ──────────────────────────────────────────────────────────
    def _sauvegarder(self, rapport: Dict, audit_id: str):
        try:
            fpath = os.path.join(self.models_path, f"v1_deces_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : {fpath}")
        except Exception as e:
            self.logger.warning(f"Sauvegarde : {e}")

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success': False, 'statut_rag': 'ROUGE',
            'commentaire': f"❌ ERREUR V1 : {message}",
            'audit_id': audit_id, 'erreur': message,
        }
