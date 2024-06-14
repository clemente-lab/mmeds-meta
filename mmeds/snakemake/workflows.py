workflows = {
    "standard_pipeline": "workflows/standard_pipeline/Snakemake"
}

def get_workflow(workflow) {
    return workflows[workflow]
}
