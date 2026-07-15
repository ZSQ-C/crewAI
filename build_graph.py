import sys
import json
import subprocess
import multiprocessing
from pathlib import Path
from datetime import datetime, timezone

INPUT_PATH = 'lib/crewai'

def main():
    graphify_out = Path('graphify-out')
    graphify_out.mkdir(exist_ok=True)

    with open(graphify_out / '.graphify_python', 'w', encoding='utf-8') as f:
        f.write(sys.executable)

    print(f"Python: {sys.executable}")
    print(f"Step 1: Python interpreter path written")

    from graphify.detect import detect

    result = detect(Path(INPUT_PATH))
    print(f"Detected: {result.get('total_files', 0)} files")

    with open(graphify_out / '.graphify_detect.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    files = result.get('files', {})
    print(f"Corpus: {result.get('total_files', 0)} files")
    if files.get('code'):
        print(f"  code: {len(files['code'])} files")
    if files.get('document'):
        print(f"  docs: {len(files['document'])} files")
    if files.get('paper'):
        print(f"  papers: {len(files['paper'])} files")
    if files.get('image'):
        print(f"  images: {len(files['image'])} files")

    print("Step 2: Detection complete")

    from graphify.extract import collect_files, extract

    code_files = []
    for f in result.get('files', {}).get('code', []):
        p = Path(f)
        if p.is_dir():
            code_files.extend(collect_files(p))
        else:
            code_files.append(p)

    print(f"Code files for extraction: {len(code_files)}")

    if code_files:
        ast_result = extract(code_files, cache_root=Path(INPUT_PATH), max_workers=4)
        with open(graphify_out / '.graphify_ast.json', 'w', encoding='utf-8') as f:
            json.dump(ast_result, f, ensure_ascii=False, indent=2)
        print(f"AST: {len(ast_result['nodes'])} nodes, {len(ast_result['edges'])} edges")
    else:
        with open(graphify_out / '.graphify_ast.json', 'w', encoding='utf-8') as f:
            json.dump({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}, f, ensure_ascii=False)
        print("No code files - skipping AST extraction")

    print("Step 3A: AST extraction complete")

    with open(graphify_out / '.graphify_semantic.json', 'w', encoding='utf-8') as f:
        json.dump({'nodes':[],'edges':[],'hyperedges':[],'input_tokens':0,'output_tokens':0}, f, ensure_ascii=False)

    print("Step 3B: Semantic extraction (code-only, skipped)")

    ast = json.loads((graphify_out / '.graphify_ast.json').read_text(encoding='utf-8'))
    sem = json.loads((graphify_out / '.graphify_semantic.json').read_text(encoding='utf-8'))

    seen = {n['id'] for n in ast['nodes']}
    merged_nodes = list(ast['nodes'])
    for n in sem['nodes']:
        if n['id'] not in seen:
            merged_nodes.append(n)
            seen.add(n['id'])

    merged_edges = ast['edges'] + sem['edges']
    merged_hyperedges = sem.get('hyperedges', [])

    merged = {
        'nodes': merged_nodes,
        'edges': merged_edges,
        'hyperedges': merged_hyperedges,
        'input_tokens': sem.get('input_tokens', 0),
        'output_tokens': sem.get('output_tokens', 0),
    }

    with open(graphify_out / '.graphify_extract.json', 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Step 3C: Merged {len(merged_nodes)} nodes, {len(merged_edges)} edges")

    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate
    from graphify.export import to_json

    extraction = merged
    detection = result

    G = build_from_json(extraction, root=INPUT_PATH, directed=False)

    if G.number_of_nodes() == 0:
        print("ERROR: Graph is empty")
        sys.exit(1)

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    communities = cluster(G)
    cohesion = score_all(G, communities)
    tokens = {'input': extraction.get('input_tokens', 0), 'output': extraction.get('output_tokens', 0)}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: 'Community ' + str(cid) for cid in communities}
    questions = suggest_questions(G, communities, labels)

    print(f"Clustering: {len(communities)} communities")

    wrote = to_json(G, communities, str(graphify_out / 'graph.json'))
    if not wrote:
        print("ERROR: refused to shrink graph.json")
        sys.exit(1)

    print("graph.json written")

    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, INPUT_PATH, suggested_questions=questions)
    with open(graphify_out / 'GRAPH_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print("GRAPH_REPORT.md written")

    analysis = {
        'communities': {str(k): v for k, v in communities.items()},
        'cohesion': {str(k): v for k, v in cohesion.items()},
        'gods': gods,
        'surprises': surprises,
        'questions': questions,
    }
    with open(graphify_out / '.graphify_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print("Step 4: Graph build, cluster, analysis complete")

    from graphify.diagnostics import diagnose_extraction, format_diagnostic_report

    summary = diagnose_extraction(extraction, directed=False, root=INPUT_PATH)
    print(format_diagnostic_report(summary))

    flags = [f'{summary[k]} {label}' for k, label in (
        ('dangling_endpoint_edges', 'dangling-endpoint edges'),
        ('missing_endpoint_edges', 'missing-endpoint edges'),
        ('self_loop_edges', 'self-loop edges'),
        ('directed_same_endpoint_collapsed_edges', 'collapsed (directed) edges'),
        ('undirected_same_endpoint_collapsed_edges', 'collapsed (undirected) edges'),
    ) if summary.get(k, 0)]
    if flags:
        print('GRAPH HEALTH WARNING: ' + '; '.join(flags))
    else:
        print('Graph health: OK')

    print("Step 4.5: Diagnostics complete")

    labels_dict = {}
    for cid in communities:
        nodes_in_comm = [G.nodes[n]['label'] for n in communities[cid]]
        if nodes_in_comm:
            label_text = nodes_in_comm[0]
            labels_dict[cid] = label_text[:30]
        else:
            labels_dict[cid] = f'Community {cid}'

    questions = suggest_questions(G, communities, labels_dict)
    report = generate(G, communities, cohesion, labels_dict, gods, surprises, detection, tokens, INPUT_PATH, suggested_questions=questions)
    with open(graphify_out / 'GRAPH_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)
    with open(graphify_out / '.graphify_labels.json', 'w', encoding='utf-8') as f:
        json.dump({str(k): v for k, v in labels_dict.items()}, f, ensure_ascii=False)

    print("Step 5: Community labels updated")

    result_export = subprocess.run([sys.executable, '-m', 'graphify', 'export', 'html'], capture_output=True, text=True, cwd='.')
    print(f"HTML export: {result_export.returncode}")
    if result_export.stdout:
        print(result_export.stdout[:500])
    if result_export.stderr:
        print(result_export.stderr[:500])

    print("Step 6: HTML export complete")

    from graphify.detect import save_manifest

    save_manifest(result.get('all_files') or result.get('files', []), root=INPUT_PATH)

    cost_path = graphify_out / 'cost.json'
    if cost_path.exists():
        cost = json.loads(cost_path.read_text(encoding='utf-8'))
    else:
        cost = {'runs': [], 'total_input_tokens': 0, 'total_output_tokens': 0}

    cost['runs'].append({
        'date': datetime.now(timezone.utc).isoformat(),
        'input_tokens': extraction.get('input_tokens', 0),
        'output_tokens': extraction.get('output_tokens', 0),
        'files': result.get('total_files', 0),
    })
    cost['total_input_tokens'] += extraction.get('input_tokens', 0)
    cost['total_output_tokens'] += extraction.get('output_tokens', 0)
    cost_path.write_text(json.dumps(cost, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"This run: {extraction.get('input_tokens', 0):,} input tokens, {extraction.get('output_tokens', 0):,} output tokens")

    for f in graphify_out.glob('.graphify_detect.json'):
        f.unlink()
    for f in graphify_out.glob('.graphify_extract.json'):
        f.unlink()
    for f in graphify_out.glob('.graphify_ast.json'):
        f.unlink()
    for f in graphify_out.glob('.graphify_semantic.json'):
        f.unlink()
    for f in graphify_out.glob('.graphify_analysis.json'):
        f.unlink()
    for f in graphify_out.glob('.graphify_chunk_*.json'):
        f.unlink()

    print("Step 9: Cleanup complete")
    print(f"Graph complete. Outputs in {graphify_out.absolute()}/")

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()