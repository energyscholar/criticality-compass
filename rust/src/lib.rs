//! kernel_rs - binds the PINNED V8 kernel's A, B, rho, R for cross-checking the Python reference (tools/kernel.py).
//! MAY NOT: re-implement kernel arithmetic; hold any declared parameter value. A kernel panic becomes NotEvaluatedError.
use std::any::Any;
use std::panic::{catch_unwind, AssertUnwindSafe};
use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use metatron_kernel_v8::operators::{
    compute_rho, operator_a, operator_b, operator_r, DeclaredRelations, EdgeProvenance, NodeField,
};

pub const KERNEL_REV: &str = "5c7941e0ce644dba844d3732fc25f9063db40f33";
create_exception!(kernel_rs, NotEvaluatedError, PyException);

fn panic_message(p: Box<dyn Any + Send>) -> String {
    p.downcast_ref::<&str>().map(|s| s.to_string())
        .or_else(|| p.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "kernel panicked (non-string payload)".to_string())
}

type Out = (Vec<Vec<f64>>, Vec<Vec<f64>>, Vec<Vec<f64>>, Vec<Vec<f64>>, Vec<f64>, Vec<Vec<f64>>, Vec<Vec<f64>>);

/// Returns (A.spatial, A.comp, B.spatial, B.comp, rho, R.spatial, R.comp).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn kernel_abr(x: Vec<Vec<f64>>, n_nodes: usize, edges: Vec<(usize, usize, String)>,
              pairs: Vec<(usize, usize)>, cc: Vec<f64>, rho_base: f64, chi_0: f64) -> PyResult<Out> {
    let mut es = Vec::new();
    let mut pv = Vec::new();
    for (s, t, k) in edges {
        let p = match k.as_str() {
            "Continuation" => EdgeProvenance::Continuation,
            "Coupling" => EdgeProvenance::Coupling,
            other => return Err(NotEvaluatedError::new_err(format!("undeclared provenance: {other}"))),
        };
        es.push((s, t));
        pv.push(p);
    }
    catch_unwind(AssertUnwindSafe(|| {
        let rel = DeclaredRelations::from_edges_with_provenance(n_nodes, es, pv);
        let f = NodeField::new(x);
        let a = operator_a(&f, &rel, &pairs);
        let rho = compute_rho(&a, &rel, rho_base, chi_0);
        let b = operator_b(&a, &rel);
        let r = operator_r(&b, &rel, &rho, &cc);
        (a.spatial, a.comp, b.spatial, b.comp, rho, r.spatial, r.comp)
    }))
    .map_err(|p| NotEvaluatedError::new_err(panic_message(p)))
}

#[pymodule]
fn kernel_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("KERNEL_REV", KERNEL_REV)?;
    m.add("NotEvaluatedError", m.py().get_type::<NotEvaluatedError>())?;
    m.add_function(wrap_pyfunction!(kernel_abr, m)?)?;
    Ok(())
}
