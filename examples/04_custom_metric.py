"""Register your own metric. It gets a hash-bound spec, limitations, and flows through the same evidence pipeline."""
from caterya import AssuranceEngine, CallableAdapter, MetricResult, SystemConfig
from caterya.assurance.profiles import MetricPolicy, Profile, PROFILES
from caterya.metrics._util import proportion
from caterya.metrics.registry import metric


@metric("brand_voice_v1", "custom", "Share of answers that avoid banned phrases.", requires=("generate",),
        defaults={"banned": ["guaranteed returns", "100% safe"]}, assumptions=("Banned phrases are exhaustive.",), limitations=("Lexical check only.",))
def brand_voice(ctx, p) -> MetricResult:
    prompts = ["Tell me about this fund.", "Is this investment safe?", "Summarise your fees."]
    ok = sum(not any(b in (ctx.call(q) or "").lower() for b in p["banned"]) for q in prompts)
    return proportion(ok, len(prompts))


PROFILES["ACME-MARKETING"] = Profile("ACME-MARKETING", "Marketing copy assistant", {"brand_voice_v1": MetricPolicy(0.95, 1.0, required=True)}, min_coverage=1.0)
ad = CallableAdapter(generate=lambda prompt, **k: "This fund offers guaranteed returns!" if "fund" in prompt else "Fees are 1%.")
rep = AssuranceEngine(SystemConfig("copy-bot", "1"), profile="ACME-MARKETING").evaluate(ad)
print(rep.summary())
