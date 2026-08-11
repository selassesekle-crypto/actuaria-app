# -*- coding: utf-8 -*-
"""Les deux rapports Santé-Prévoyance — les faire TOURNER, enfin.

⚠️ POURQUOI CE FICHIER EXISTE. `AgentRapportSante` et `AgentRapportPrevoyance`
produisent chacun un HTML, un Word et un Excel qu'un actuaire signe — et
AUCUN test du dépôt ne les exécutait. Leurs deux exports Word pouvaient donc
casser, se vider ou perdre une section sans que rien ne le dise.

⚠️ C'EST LE MÊME MOTIF QUE LE TROU DE GATE (`ca1ad29`) : la différence entre
« rien à vérifier ici » et « personne ne l'a jamais vérifié » ne se voit pas
depuis une gate verte. Ici la chaîne amont existait déjà — elle était écrite
pour un AUTRE agent (`test_sp_rapport.py`), et ces deux-là n'en profitaient
pas.

Ce fichier ne teste PAS la mise en page, et ne compare PAS les deux formats
entre eux — cette comparaison appartient au lot suivant. Il vérifie que les
deux chaînes vont au bout, que les deux livrables signés sortent non vides,
que le `.docx` s'ouvre réellement, et qu'il porte un plancher de texte.

⚠️ CE QUE LA PREMIÈRE EXÉCUTION A TROUVÉ, ET QUI EST SIGNALÉ SANS ÊTRE
TRAITÉ : le `.docx` Prévoyance porte **1 477 caractères** quand son HTML en
porte **22 477**. Le livrable Word est nettement plus pauvre que son jumeau.
C'est un défaut de fond, découvert précisément parce que plus rien ne
tournait à l'aveugle — mais poser le filet vient avant de le corriger.
"""
import io

import numpy as np
import pandas as pd
import pytest

from direction_sante_prevoyance.prevoyance.rapport_prevoyance.agent import (
    AgentRapportPrevoyance,
)
from direction_sante_prevoyance.sante.rapport_sante.agent import (
    AgentRapportSante,
)

#: ⚠️ La graine est FIXE : deux exécutions doivent rendre le même document,
#: sans quoi une comparaison avant/après ne prouverait rien.
GRAINE = 42
N_LIGNES = 1000


@pytest.fixture(scope="module")
def chaine_amont():
    """S1→S3 et P1→P4 : exactement ce que les deux rapports consomment.

    ⚠️ Recopiée de `rapport_actuariel/test_sp_rapport.py` plutôt qu'importée :
    ce sont deux zones de test distinctes, et une fixture partagée entre
    paquets créerait une dépendance qu'aucun des deux ne déclare.
    """
    from direction_sante_prevoyance.coordination.sp_coord.agent import (
        AgentSPCoord,
    )
    from direction_sante_prevoyance.prevoyance.p1_tarification.agent import (
        AgentP1TarificationPrevoyance,
    )
    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import (
        AgentP2TablesMorbidite,
    )
    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import (
        AgentP3ProvissionnementPrevoyance,
    )
    from direction_sante_prevoyance.prevoyance.p4_reporting.agent import (
        AgentP4ReportingPrevoyance,
    )
    from direction_sante_prevoyance.sante.s1_tarification.agent import (
        AgentS1TarificationSante,
    )
    from direction_sante_prevoyance.sante.s2_provisionnement.agent import (
        AgentS2ProvissionnementSante,
    )
    from direction_sante_prevoyance.sante.s3_reporting.agent import (
        AgentS3ReportingSante,
    )
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder

    np.random.seed(GRAINE)
    n = N_LIGNES
    df_m = pd.DataFrame({
        "age": np.random.randint(25, 60, n),
        "garanties": np.random.choice(["confort", "premium"], n),
        "sinistres_sante": np.random.exponential(600, n),
        "cotisation": np.random.uniform(900, 1800, n),
    })
    df_ip = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe", "cadre", "ouvrier"], n,
                                p=[0.5, 0.3, 0.2]),
        "arrets_itt": np.where(np.random.rand(n) < 0.08,
                               np.random.uniform(30, 180, n), 0),
    })
    r_bm = SPDataBuilder(verbose=False).construire(df_m)
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)

    s1 = AgentS1TarificationSante(verbose=False).run(
        result_a2=r_bm, nb_assures=n, age_moyen=40, contrat="collectif",
        garantie_niveau="confort", generer_graphiques=False)
    s2 = AgentS2ProvissionnementSante(verbose=False).run(
        result_s1=s1, generer_graphiques=False)
    s3 = AgentS3ReportingSante(verbose=False).run(
        result_s1=s1, result_s2=s2, fonds_propres=5_000_000,
        generer_graphiques=False)
    p1 = AgentP1TarificationPrevoyance(verbose=False).run(
        result_a2=r_bip, age=42, salaire_brut=45000, categorie="employe",
        generer_graphiques=False)
    p2 = AgentP2TablesMorbidite(verbose=False).run(
        result_p1=p1, generer_graphiques=False)
    p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
        result_p1=p1, result_p2=p2, generer_graphiques=False)
    p4 = AgentP4ReportingPrevoyance(verbose=False).run(
        result_p1=p1, result_p2=p2, result_p3=p3, fonds_propres=10_000_000,
        generer_graphiques=False)
    AgentSPCoord(verbose=False).run(
        result_s3=s3, result_p4=p4, fonds_propres=15_000_000,
        generer_graphiques=False)
    return {"s1": s1, "s2": s2, "s3": s3,
            "p1": p1, "p2": p2, "p3": p3, "p4": p4}


@pytest.fixture(scope="module")
def rapport_sante(chaine_amont):
    return AgentRapportSante(verbose=False).run(
        result_s1=chaine_amont["s1"], result_s2=chaine_amont["s2"],
        result_s3=chaine_amont["s3"], entite="Mutuelle Test",
        date_arrete="31/12/2025", fonds_propres=5_000_000,
        generer_graphiques=False)


@pytest.fixture(scope="module")
def rapport_prevoyance(chaine_amont):
    return AgentRapportPrevoyance(verbose=False).run(
        result_p1=chaine_amont["p1"], result_p2=chaine_amont["p2"],
        result_p3=chaine_amont["p3"], result_p4=chaine_amont["p4"],
        entite="Institution Test", date_arrete="31/12/2025",
        fonds_propres=10_000_000, generer_graphiques=False)


def _paragraphes(word_bytes):
    """Le texte du .docx, paragraphe par paragraphe."""
    from docx import Document
    doc = Document(io.BytesIO(word_bytes))
    return [p.text for p in doc.paragraphs if p.text.strip()]


@pytest.mark.parametrize("nom", ["sante", "prevoyance"])
def test_la_chaine_va_au_bout(nom, rapport_sante, rapport_prevoyance):
    """⚠️ Rien ne vérifiait que ces deux agents s'exécutent sans lever."""
    r = rapport_sante if nom == "sante" else rapport_prevoyance
    assert r.get("success") is True, r.get("erreur")
    assert r.get("statut_rag") in ("VERT", "AMBRE", "ROUGE")


@pytest.mark.parametrize("nom", ["sante", "prevoyance"])
def test_les_deux_formats_signes_sortent_non_vides(nom, rapport_sante,
                                                   rapport_prevoyance):
    """⚠️ Le Word rend `b''` en cas d'echec — un livrable vide est le seul
    symptôme, et rien ne le regardait."""
    r = rapport_sante if nom == "sante" else rapport_prevoyance
    for cle in ("html_bytes", "word_bytes"):
        assert r.get(cle), f"{nom} : {cle} est vide"
    assert len(r["word_bytes"]) > 5000, f"{nom} : .docx suspicieusement court"


@pytest.mark.parametrize("nom", ["sante", "prevoyance"])
def test_le_docx_s_ouvre_et_porte_du_texte(nom, rapport_sante,
                                           rapport_prevoyance):
    """Des octets non vides ne prouvent pas un document lisible."""
    r = rapport_sante if nom == "sante" else rapport_prevoyance
    paras = _paragraphes(r["word_bytes"])
    assert len(paras) > 20, f"{nom} : {len(paras)} paragraphes seulement"


@pytest.mark.parametrize("nom", ["sante", "prevoyance"])
def test_le_docx_n_est_pas_une_coquille_vide(nom, rapport_sante,
                                             rapport_prevoyance):
    """⚠️ MESURÉ EN ÉCRIVANT CE FICHIER, ET SIGNALÉ : le .docx Prévoyance
    porte 1 477 caractères quand son HTML en porte 22 477. Un livrable signé
    nettement plus pauvre que son jumeau est un défaut de fond, mais le
    corriger n'est pas l'objet de ce lot-ci : il n'existait AUCUN test, et
    poser le filet vient d'abord.

    Ce test fixe le plancher constaté aujourd'hui. Il ne valide pas la
    parité entre formats — il empêche une régression sous l'état actuel.
    """
    r = rapport_sante if nom == "sante" else rapport_prevoyance
    total = sum(len(p) for p in _paragraphes(r["word_bytes"]))
    assert total > 1000, (
        f"{nom} : le .docx ne porte que {total} caracteres de texte")
