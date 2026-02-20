from __future__ import annotations

from collections import Counter, defaultdict, deque

from analyzemail.models import ClassificationResult, ThreadSummary

_SUBJECT_PREFIXES = ("re:", "fwd:", "fw:")


def _normalized_subject(subject: str) -> str:
    text = " ".join(subject.lower().split())
    changed = True
    while changed:
        changed = False
        for prefix in _SUBJECT_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                changed = True
    return text


def _find_components(adjacency: list[set[int]]) -> list[list[int]]:
    visited: set[int] = set()
    components: list[list[int]] = []

    for node in range(len(adjacency)):
        if node in visited:
            continue
        queue = deque([node])
        visited.add(node)
        component: list[int] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return components


def build_threads(classifications: tuple[ClassificationResult, ...]) -> tuple[ThreadSummary, ...]:
    if not classifications:
        return ()

    message_id_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, result in enumerate(classifications):
        message_id = result.message.message_id
        if message_id:
            message_id_to_indices[message_id].append(idx)

    adjacency: list[set[int]] = [set() for _ in classifications]

    for idx, result in enumerate(classifications):
        refs = []
        if result.message.in_reply_to:
            refs.append(result.message.in_reply_to)
        refs.extend(result.message.references)

        for ref in refs:
            for target in message_id_to_indices.get(ref, []):
                if target == idx:
                    continue
                adjacency[idx].add(target)
                adjacency[target].add(idx)

    initial_components = _find_components(adjacency)

    singleton_groups: dict[tuple[str, int], list[int]] = defaultdict(list)
    for component in initial_components:
        if len(component) != 1:
            continue
        index = component[0]
        message = classifications[index].message
        if message.date_utc is None:
            continue
        subject_key = _normalized_subject(message.subject)
        if not subject_key:
            continue
        week_bucket = message.date_utc.toordinal() // 7
        singleton_groups[(subject_key, week_bucket)].append(index)

    for group in singleton_groups.values():
        if len(group) < 2:
            continue
        lead = group[0]
        for idx in group[1:]:
            adjacency[lead].add(idx)
            adjacency[idx].add(lead)

    components = _find_components(adjacency)

    thread_summaries: list[ThreadSummary] = []
    for i, component in enumerate(components, start=1):
        sender_counts = Counter(classifications[idx].message.from_address or "<unknown>" for idx in component)
        dominant_sender = sender_counts.most_common(1)[0][0]

        estimated_bytes = sum(classifications[idx].message.size_bytes for idx in component)
        candidate_results = [classifications[idx] for idx in component if classifications[idx].is_candidate]
        candidate_message_count = len(candidate_results)
        candidate_estimated_bytes = sum(result.message.size_bytes for result in candidate_results)

        if candidate_message_count == 0:
            confidence = "low"
        elif all(result.confidence == "high" for result in candidate_results):
            confidence = "high"
        else:
            confidence = "medium"

        thread_summaries.append(
            ThreadSummary(
                thread_id=f"thread-{i:04d}",
                message_indices=tuple(component),
                message_count=len(component),
                estimated_bytes=estimated_bytes,
                candidate_message_count=candidate_message_count,
                candidate_estimated_bytes=candidate_estimated_bytes,
                dominant_sender=dominant_sender,
                confidence=confidence,
            )
        )

    thread_summaries.sort(
        key=lambda thread: (
            thread.candidate_estimated_bytes,
            thread.estimated_bytes,
            thread.message_count,
        ),
        reverse=True,
    )
    return tuple(thread_summaries)
