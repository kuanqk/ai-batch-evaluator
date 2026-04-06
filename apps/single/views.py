"""Browser UI for single-document evaluation (formerly orleu-evaluator-main)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.batch.models import Evaluation, EvaluationJob


@login_required
def submit(request):
    """Form to submit a single document URL for evaluation."""
    context: dict = {}
    if request.method == "POST":
        file_url = (request.POST.get("file_url") or "").strip()
        material_id = request.POST.get("material_id", "").strip()
        if not file_url:
            context["error"] = "Укажите URL документа"
            return render(request, "single/submit.html", context)

        job = EvaluationJob.objects.create(
            name=f"single:{material_id or file_url[:40]}",
            source_file="single",
            total=1,
            status=EvaluationJob.STATUS_RUNNING,
            created_by=request.user,
        )
        ev = Evaluation.objects.create(
            job=job,
            file_url=file_url,
            material_id=int(material_id) if material_id.isdigit() else None,
        )
        from tasks.evaluate import process_file
        process_file.delay(ev.pk)

        context["eval_id"] = ev.pk
        context["job_id"] = job.pk
        context["submitted"] = True

    return render(request, "single/submit.html", context)


@login_required
def result(request, eval_id: int):
    """Show result for a single evaluation."""
    try:
        ev = Evaluation.objects.select_related("job").get(pk=eval_id)
    except Evaluation.DoesNotExist:
        return render(request, "single/result.html", {"not_found": True})

    score_keys = [f"s{s}_c{c}" for s in range(1, 6) for c in range(1, 6)]
    scores_table = []
    if ev.scores:
        for s in range(1, 6):
            row = []
            for c in range(1, 6):
                key = f"s{s}_c{c}"
                row.append({"key": key, "value": ev.scores.get(key, 0)})
            scores_table.append({"section": s, "criteria": row})

    return render(
        request,
        "single/result.html",
        {
            "ev": ev,
            "scores_table": scores_table,
        },
    )
