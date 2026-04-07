#!/bin/bash
set -e

DIAG=/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx/src/diagnostics

mkdir -p ${DIAG}

# Add UV10M to the list of diagnostics
#Step 1 — Write the two new source files

cat > ${DIAG}/horiz_winds_at_height.hpp << 'EOF'
#pragma once

#include "share/atm_process/atmosphere_diagnostic.hpp"

namespace scream {

// Extracts zonal (U) or meridional (V) wind from horiz_winds
// at a specified height above surface or sea level.
//
// Supported field names:
//   U_at_<Y>m_above_surface   V_at_<Y>m_above_surface
//   U_at_<Y>m_above_sealevel  V_at_<Y>m_above_sealevel
//
class HorizWindsAtHeight : public AtmosphereDiagnostic {
public:
  HorizWindsAtHeight (const ekat::Comm& comm, const ekat::ParameterList& params);

  std::string name () const override { return "HorizWindsAtHeight"; }

  void set_grids (const std::shared_ptr<const GridsManager> grids_manager) override;

protected:
  void initialize_impl (const RunType run_type) override;
  void run_impl        (const double dt) override;
  void finalize_impl   () override {};

  Real        m_height;    // target height [m]
  std::string m_surf;      // "surface" or "sealevel"
  int         m_comp_idx;  // 0 = U (zonal), 1 = V (meridional)
  int         m_num_cols;
  int         m_num_levs;
};

} // namespace scream
EOF


cat > ${DIAG}/horiz_winds_at_height.cpp << 'EOF'
#include "diagnostics/horiz_winds_at_height.hpp"
#include <ekat/ekat_assert.hpp>

namespace scream {

HorizWindsAtHeight::HorizWindsAtHeight (const ekat::Comm& comm,
                                        const ekat::ParameterList& params)
  : AtmosphereDiagnostic(comm, params)
{
  const auto& name = params.get<std::string>("diag_name");

  EKAT_REQUIRE_MSG (name.size() > 2 && (name[0]=='U' || name[0]=='V') && name[1]=='_',
      "Error! HorizWindsAtHeight: diag name must start with 'U_' or 'V_'.\n"
      "  Actual name: " + name + "\n");
  m_comp_idx = (name[0] == 'U') ? 0 : 1;

  auto pos = name.rfind("_at_");
  EKAT_REQUIRE_MSG (pos != std::string::npos,
      "Error! HorizWindsAtHeight: expected format [U|V]_at_<val>m_above_[surface|sealevel]\n"
      "  Actual name: " + name + "\n");
  auto suffix = name.substr(pos + 4);

  auto pos2 = suffix.find("m_above_");
  EKAT_REQUIRE_MSG (pos2 != std::string::npos,
      "Error! HorizWindsAtHeight: expected format [U|V]_at_<val>m_above_[surface|sealevel]\n"
      "  Actual name: " + name + "\n");
  m_height = std::stof(suffix.substr(0, pos2));
  m_surf   = suffix.substr(pos2 + 8);

  EKAT_REQUIRE_MSG (m_surf == "surface" || m_surf == "sealevel",
      "Error! HorizWindsAtHeight: reference surface must be 'surface' or 'sealevel'.\n"
      "  Actual value: " + m_surf + "\n");
}

void HorizWindsAtHeight::set_grids (
    const std::shared_ptr<const GridsManager> grids_manager)
{
  const auto& name = params().get<std::string>("diag_name");
  const auto& gn   = params().get<std::string>("grid_name");

  auto grid = grids_manager->get_grid("Physics GLL");
  m_num_cols = grid->get_num_local_dofs();
  m_num_levs = grid->get_num_vertical_levels();

  add_field<Required>("horiz_winds",
                      FieldLayout({CMP, LEV}, {2, m_num_levs}),
                      m/s, "Physics GLL");

  add_field<Required>("z_mid",
                      FieldLayout({COL, LEV}, {m_num_cols, m_num_levs}),
                      ekat::units::m, gn);

  FieldLayout diag_layout ({COL}, {m_num_cols});
  FieldIdentifier fid(name, diag_layout, m/s, gn);
  m_diagnostic_output = Field(fid);
  m_diagnostic_output.allocate_view();
}

void HorizWindsAtHeight::initialize_impl (const RunType /*run_type*/) {}

void HorizWindsAtHeight::run_impl (const double /*dt*/)
{
  const auto hw_v  = get_field_in("horiz_winds").get_view<const Real***>();
  const auto z_v   = get_field_in("z_mid").get_view<const Real**>();
  const auto out_v = m_diagnostic_output.get_view<Real*>();

  const int  nlev   = m_num_levs;
  const int  comp   = m_comp_idx;
  const Real height = m_height;
  const std::string surf = m_surf;

  Kokkos::parallel_for(m_num_cols, KOKKOS_LAMBDA(const int icol) {
    int  k_above = -1;
    Real z_above = 0, z_below = 0;

    for (int k = nlev - 1; k >= 0; --k) {
      const Real z_val = (surf == "surface")
                         ? (z_v(icol,k) - z_v(icol,nlev-1))
                         : z_v(icol,k);
      if (z_val >= height) {
        k_above = k;
        z_above = z_val;
        z_below = (k < nlev-1)
                  ? ((surf == "surface")
                     ? (z_v(icol,k+1) - z_v(icol,nlev-1))
                     : z_v(icol,k+1))
                  : 0.0;
      } else {
        break;
      }
    }

    if (k_above == -1) {
      out_v(icol) = hw_v(icol, comp, nlev-1);
    } else if (k_above == nlev-1 || z_above == z_below) {
      out_v(icol) = hw_v(icol, comp, k_above);
    } else {
      const Real alpha = (height - z_below) / (z_above - z_below);
      out_v(icol) = hw_v(icol, comp, k_above+1)
                  + alpha * (hw_v(icol, comp, k_above)
                           - hw_v(icol, comp, k_above+1));
    }
  });
}

} // namespace scream
EOF

#Step 2 — Patch register_diagnostics.hpp ---------------------------------------
python3 << 'PYEOF'
fpath = '/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx/src/diagnostics/register_diagnostics.hpp'
with open(fpath) as f:
    txt = f.read()

txt = txt.replace(
    '#include "diagnostics/wind_speed.hpp"',
    '#include "diagnostics/wind_speed.hpp"\n#include "diagnostics/horiz_winds_at_height.hpp"',
    1)

new_group = '''
  dm.register_group("HorizWindsAtHeight",
    [](const ekat::Comm& c, const ekat::ParameterList& p) -> std::shared_ptr<AtmosphereDiagnostic> {
      return std::make_shared<HorizWindsAtHeight>(c,p);
    },
    [](const std::string& name) -> bool {
      if (name.size() < 2) return false;
      if (name[0]!='U' && name[0]!='V') return false;
      if (name[1]!='_') return false;
      auto pos = name.rfind("_at_");
      if (pos==std::string::npos) return false;
      auto suffix = name.substr(pos+4);
      auto pos2 = suffix.find("m_above_");
      if (pos2==std::string::npos) return false;
      try { std::stof(suffix.substr(0,pos2)); } catch(...) { return false; }
      auto surf = suffix.substr(pos2+8);
      return surf=="surface" or surf=="sealevel";
    }
  );
'''

last = txt.rfind('\n}')
txt = txt[:last] + new_group + '\n}'
with open(fpath, 'w') as f:
    f.write(txt)
print('Done:', fpath)
PYEOF


#Step 3 — Patch CMakeLists.txt ---------------------------------------
python3 << 'PYEOF'
fpath = '/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx/src/diagnostics/CMakeLists.txt'
with open(fpath) as f:
    txt = f.read()
txt = txt.replace(
    '  diagnostics/wind_speed.cpp',
    '  diagnostics/wind_speed.cpp\n  diagnostics/horiz_winds_at_height.cpp',
    1)
with open(fpath, 'w') as f:
    f.write(txt)
print('Done:', fpath)
PYEOF

#Step 4 — Fix the YAML file ---------------------------------------
sed -i 's/U_at_10m_above_Z/U_at_10m_above_surface/; s/V_at_10m_above_Z/V_at_10m_above_surface/' \
    /global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/run_scripts/yaml_files/scream_output_inst_5min_testvar.yaml

#Step 5 — Commit ---------------------------------------
cd /global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM
git add components/eamxx/src/diagnostics/horiz_winds_at_height.hpp \
        components/eamxx/src/diagnostics/horiz_winds_at_height.cpp \
        components/eamxx/src/diagnostics/register_diagnostics.hpp \
        components/eamxx/src/diagnostics/CMakeLists.txt
git commit -m 'Add HorizWindsAtHeight diagnostic for U/V winds at height'
git log --oneline -3

#Step 6 — Write uv_diag.md ---------------------------------------
cat > /global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/run_scripts/uv_diag.md << 'MDEOF'
# HorizWindsAtHeight Diagnostic — Source Code Changes

**Branch:** `ksa/uvwinds`
**Repository:** `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM`

## Motivation

The simulation aborted because `U_at_10m_above_Z` and `V_at_10m_above_Z`
were not found. Two bugs:
1. `Z` is not a valid reference surface token (must be `surface` or `sealevel`).
2. The existing `FieldAtHeight` diagnostic strips the suffix and looks up a
   scalar field named `"U"` or `"V"`, which does not exist. Zonal and
   meridional winds are stored together in `horiz_winds (COL, CMP, LEV)`.

## Files Changed

### diagnostics/horiz_winds_at_height.hpp (new)
Declares `HorizWindsAtHeight`, subclass of `AtmosphereDiagnostic`.
Members: `m_height` (target height [m]), `m_surf` ("surface"/"sealevel"),
`m_comp_idx` (0=U, 1=V), `m_num_cols`, `m_num_levs`.

### diagnostics/horiz_winds_at_height.cpp (new)
- Constructor: parses `diag_name` e.g. `U_at_10m_above_surface` to set
  `m_comp_idx`, `m_height`, `m_surf`. Validated with `EKAT_REQUIRE_MSG`.
- `set_grids`: requires `horiz_winds (CMP,LEV)` from Physics GLL and
  `z_mid (COL,LEV)` from output grid. Allocates scalar `(COL)` output.
- `run_impl`: Kokkos loop over columns. Searches upward from lowest level
  to find bracketing levels, then linearly interpolates the selected
  component of `horiz_winds` to the target height.

### diagnostics/register_diagnostics.hpp (modified)
- Added `#include "diagnostics/horiz_winds_at_height.hpp"`
- Added `dm.register_group("HorizWindsAtHeight", ...)` with a matcher
  that accepts only `U_*` or `V_*` names, preventing `FieldAtHeight`
  from attempting to look up nonexistent scalar fields named `"U"` or `"V"`.

### diagnostics/CMakeLists.txt (modified)
Added `diagnostics/horiz_winds_at_height.cpp` to `DIAGNOSTICS_SRCS`.

## YAML Fix
`scream_output_inst_5min_testvar.yaml`: changed `U/V_at_10m_above_Z`
to `U/V_at_10m_above_surface`.
MDEOF
echo "Done: uv_diag.md"




