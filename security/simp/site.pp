# Durcissement de la machine cible avec SIMP (profil DISA STIG)
# Les parametres des modules SIMP sont dans data/common.yaml (Hiera)
include crypto_policy   # politique de chiffrement du systeme
include pam             # authentification : mots de passe, verrouillage de compte
include pam::wheel      # seul le groupe wheel peut utiliser su
include useradd         # creation de comptes, login.defs, umask

# ----- Profil local : regles STIG non couvertes par les modules SIMP -----

# Signature obligatoire des paquets installes localement
ini_setting { 'dnf localpkg_gpgcheck':
  ensure            => present,
  path              => '/etc/dnf/dnf.conf',
  section           => 'main',
  setting           => 'localpkg_gpgcheck',
  value             => '1',
  key_val_separator => ' = ',
}

# Umask 077 pour les shells non interactifs
file_line { 'bashrc umask 077':
  path  => '/etc/bashrc',
  match => '^\s*\[ `umask` -eq 0 \] && umask',
  line  => '    [ `umask` -eq 0 ] && umask 077',
}

# Fichiers de demarrage de root recrees en 600 par systemd-tmpfiles
file { '/etc/tmpfiles.d/rootfiles.conf':
  ensure  => file,
  mode    => '0644',
  content => "C /root/.bash_logout 600 root root - /usr/share/rootfiles/.bash_logout\nC /root/.bash_profile 600 root root - /usr/share/rootfiles/.bash_profile\nC /root/.bashrc 600 root root - /usr/share/rootfiles/.bashrc\nC /root/.cshrc 600 root root - /usr/share/rootfiles/.cshrc\nC /root/.tcshrc 600 root root - /usr/share/rootfiles/.tcshrc\n",
}

# Droits actuels des fichiers de demarrage de root : ni groupe en ecriture, ni autres
exec { 'droits fichiers init root':
  command => "/usr/bin/find /root -mindepth 1 -maxdepth 1 -name '.*' -perm /g=wx,o=rwx -exec chmod g-wx,o= {} +",
  onlyif  => "/usr/bin/find /root -mindepth 1 -maxdepth 1 -name '.*' -perm /g=wx,o=rwx | /usr/bin/grep -q .",
}
