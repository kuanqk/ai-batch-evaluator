"""Browser UI views (session auth)."""

from __future__ import annotations

import io

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from openpyxl import Workbook
from openpyxl.styles import Font

from .models import Evaluation, EvaluationJob
from .utils import parse_batch_upload


@login_required
def dashboard(request):
    jobs = EvaluationJob.objects.order_by("-created_at")[:50]
    return render(request, "batch/dashboard.html", {"jobs": jobs})


@login_required
def upload(request):
    if request.method == "POST":
        file_obj = request.FILES.get("file")
        if not file_obj:
            return render(request, "batch/upload.html", {"error": "Выберите файл"})
        content = file_obj.read()
        try:
            rows, skipped = parse_batch_upload(content, file_obj.name)
        except ValueError as e:
            return render(request, "batch/upload.html", {"error": str(e)})
        if not rows:
            return render(request, "batch/upload.html", {"error": "Нет валидных строк (нужен file_url)"})

        name = request.POST.get("name") or file_obj.name
        webhook_url = request.POST.get("webhook_url") or None

        job = EvaluationJob.objects.create(
            name=name,
            source_file=file_obj.name,
            total=len(rows),
            status=EvaluationJob.STATUS_RUNNING,
            webhook_url=webhook_url,
            created_by=request.user,
        )
        Evaluation.objects.bulk_create([
            Evaluation(
                job=job,
                evaluator_config_id=job.evaluator_config_id,
                file_path=r.get("file_path"),
                file_url=r["file_url"],
                city=r.get("city"),
                trainer=r.get("trainer"),
                group_name=r.get("group_name"),
                file_name=r.get("file_name"),
            )
            for r in rows
        ])
        from tasks.evaluate import process_job
        process_job.delay(job.pk)

        return redirect(reverse("batch:results") + f"?job_id={job.pk}")

    return render(request, "batch/upload.html")


@login_required
def results(request):
    qs = Evaluation.objects.select_related("job").order_by("-created_at")

    job_id = request.GET.get("job_id")
    city = request.GET.get("city", "").strip()
    trainer = request.GET.get("trainer", "").strip()
    status_filter = request.GET.get("status", "").strip()
    level = request.GET.get("level", "").strip()
    search = request.GET.get("q", "").strip()

    if job_id:
        qs = qs.filter(job_id=job_id)
    if city:
        qs = qs.filter(city__icontains=city)
    if trainer:
        qs = qs.filter(trainer__icontains=trainer)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if level:
        qs = qs.filter(score_level=level)
    if search:
        qs = qs.filter(
            Q(city__icontains=search)
            | Q(trainer__icontains=search)
            | Q(teacher_name__icontains=search)
            | Q(topic__icontains=search)
        )

    page = int(request.GET.get("page", 1))
    page_size = 50
    offset = (page - 1) * page_size
    total = qs.count()
    items = list(qs[offset: offset + page_size])

    total_pages = (total + page_size - 1) // page_size
    stats = qs.filter(status="done").aggregate(
        avg_pct=Avg("score_percentage"),
        count_done=Count("id"),
    )

    jobs = EvaluationJob.objects.values("id", "name").order_by("-created_at")[:100]

    context = {
        "items": items,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "stats": stats,
        "jobs": jobs,
        "filters": {
            "job_id": job_id or "",
            "city": city,
            "trainer": trainer,
            "status": status_filter,
            "level": level,
            "q": search,
        },
    }
    return render(request, "batch/results.html", context)


@login_required
def export_excel(request):
    qs = Evaluation.objects.select_related("job").filter(status="done").order_by("-created_at")

    job_id = request.GET.get("job_id")
    if job_id:
        qs = qs.filter(job_id=job_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Результаты оценки"

    score_keys = [f"s{s}_c{c}" for s in range(1, 6) for c in range(1, 6)]
    headers = [
        "ID", "Job", "Город", "Тренер", "Группа", "Файл",
        "Педагог", "Тема", "Статус",
        "Балл", "%", "Уровень",
        *score_keys,
        "Метод извлечения", "Язык", "Символов", "Дата оценки",
    ]

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for ev in qs:
        scores = ev.scores or {}
        row = [
            ev.pk,
            ev.job.name if ev.job else "",
            ev.city or "",
            ev.trainer or "",
            ev.group_name or "",
            ev.file_name or "",
            ev.teacher_name or "",
            ev.topic or "",
            ev.status,
            ev.total_score,
            ev.score_percentage,
            ev.score_level,
            *[scores.get(k, "") for k in score_keys],
            ev.extraction_method or "",
            ev.doc_lang or "",
            ev.doc_chars,
            ev.processed_at,
        ]
        ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    name = f"evaluations_job{job_id}.xlsx" if job_id else "evaluations.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response
