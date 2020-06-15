import os,glob,warnings
import dpgen.auto_test.lib.vasp as vasp
import dpgen.auto_test.lib.lammps as lammps
import numpy as np

def make_repro(vasp_path, path_to_work):
    if not os.path.exists(vasp_path):
        raise RuntimeError("please do VASP calcualtions first")
    vasp_task = glob.glob(os.path.join(vasp_path, 'task.[0-9]*[0-9]'))
    assert len(vasp_task) > 0, "Please do VASP calcualtions first"
    vasp_task.sort()
    task_num = 0
    task_list = []
    for ii in vasp_task:
        # get vasp energy
        outcar = os.path.join(ii, 'OUTCAR')
        energies = vasp.get_energies(outcar)
        # get xdat
        xdatcar = os.path.join(ii, 'XDATCAR')
        os.chdir(path_to_work)
        if os.path.exists('XDATCAR'):
            os.remove('XDATCAR')
        os.symlink(os.path.relpath(xdatcar), 'XDATCAR')
        xdat_lines = open('XDATCAR', 'r').read().split('\n')
        natoms = vasp.poscar_natoms('XDATCAR')
        xdat_secsize = natoms + 8
        xdat_nframes = len(xdat_lines) // xdat_secsize
        if xdat_nframes > len(energies):
            warnings.warn('nframes %d in xdatcar is larger than energy %d, use the last %d frames' % (
                xdat_nframes, len(energies), len(energies)))
            xdat_nlines = -1 * len(energies) * xdat_secsize  # 06/12 revised
            xdat_lines = xdat_lines[xdat_nlines:]
        xdat_nframes = len(xdat_lines) // xdat_secsize
        print(xdat_nframes, len(energies))

        # loop over frames
        for jj in range(xdat_nframes):
            output_task = os.path.join(path_to_work, 'task.%06d' % task_num)
            task_num += 1
            task_list.append(output_task)
            os.makedirs(output_task, exist_ok=True)
            os.chdir(output_task)
            # clear dir
            for kk in ['INCAR', 'POTCAR', 'POSCAR.orig', 'POSCAR', 'conf.lmp', 'in.lammps']:
                if os.path.exists(kk):
                    os.remove(kk)
            # make conf
            with open('POSCAR', 'w') as fp:
                fp.write('\n'.join(xdat_lines[jj * xdat_secsize:(jj + 1) * xdat_secsize]))

    return task_list

def post_repro(vasp_path, all_tasks, ptr_data):
    ptr_data += "Reproduce: VASP_path DFT_E(eV/atom)  LMP_E(eV/atom)  Difference(eV/atom)\n"
    vasp_task = glob.glob(os.path.join(vasp_path, 'task.[0-9]*[0-9]'))
    assert len(vasp_task) > 0, "Please do VASP calcualtions first"
    vasp_task.sort()
    vasp_ener_tot = []
    lmp_ener_tot = []
    res_data = {}
    for ii in vasp_task:
        # compute vasp
        outcar = os.path.join(ii, 'OUTCAR')
        vasp_ener = np.array(vasp.get_energies(outcar))
        vasp_ener_file = os.path.join(ii, 'ener.vasp.out')
        # compute reprod
        lmp_ener = []

        if len(all_tasks) < (len(vasp_ener_tot) + len(vasp_ener)):
            raise RuntimeError ("lammps tasks reproduced not equal to vasp")

        natoms = 1
        for jj in range(len(vasp_ener_tot),(len(vasp_ener_tot) + len(vasp_ener))): #all_tasks[len(vasp_ener_tot):(len(vasp_ener_tot) + len(vasp_ener))]:
            log_lmp = os.path.join(all_tasks[jj], 'log.lammps')
            if not os.path.exists(log_lmp):
                raise RuntimeError("lammps reproduce not finished")
            natoms, epa, vpa = lammps.get_nev(log_lmp)
            lmp_ener.append(epa)
            lmp_ener_tot.append(epa)
            vasp_epa = list(vasp_ener)[jj-len(vasp_ener_tot)] / natoms
            ptr_data += '%s %7.3f  %7.3f  %7.3f\n' % (vasp_task[ii], vasp_epa,
                                                      epa, epa-vasp_epa)
        lmp_ener = np.array(lmp_ener)
        lmp_ener = np.reshape(lmp_ener, [-1, 1])
        vasp_ener_tot += list(vasp_ener)
        vasp_ener = np.reshape(vasp_ener, [-1, 1]) / natoms
        error_start = 1
        lmp_ener -= lmp_ener[-1] - vasp_ener[-1]
        diff = lmp_ener - vasp_ener
        diff = diff[error_start:]
        error = np.linalg.norm(diff) / np.sqrt(np.size(lmp_ener))
        res_data[ii] = {'nframes': len(vasp_ener), 'error': error}
        np.savetxt(vasp_ener_file, vasp_ener[error_start:])
    if not len(vasp_ener_tot) == len(lmp_ener_tot):
        raise RuntimeError("lammps tasks reproduced not equal to vasp")
#    for ii in range(len(lmp_ener_tot)):
#        ptr_data += '%7.3f  %7.3f  %7.3f\n' % (vasp_ener_tot[ii], lmp_ener_tot[ii],
#                                               lmp_ener_tot[ii] - vasp_ener_tot[ii])
    return res_data, ptr_data
