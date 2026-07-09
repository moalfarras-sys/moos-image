#!/usr/bin/env bash
green='\033[0;32m'
red='\033[0;31m'
bred='\033[1;31m'
cyan='\033[0;36m'
grey='\033[2;37m'
reset="\033[0m"

: ${THEMES_DIR:=/usr/share/sddm/themes}

# Test for debug param ( debug | -debug | -d | --debug )
if [[ "$1" =~ ^(debug|-debug|--debug|-d)$ ]]; then
    QT_IM_MODULE=qtvirtualkeyboard QML2_IMPORT_PATH=./components/ sddm-greeter-qt6 --test-mode --theme .
else
    config_file=$(awk -F '=' '/^ConfigFile=/ {print $2}' metadata.desktop)
    echo -e "${green}Testing MoOS Nova theme (based on SilentSDDM)...${reset}\nLoading config: ${config_file}\nDon't worry about the infinite loading, SDDM won't let you log in while in 'test-mode'."
    QT_IM_MODULE=qtvirtualkeyboard QML2_IMPORT_PATH=./components/ sddm-greeter-qt6 --test-mode --theme . > /dev/null 2>&1
fi

if [ ! -d "${THEMES_DIR}/moos-nova" ]; then
    echo -e "\n${bred}[WARNING]: ${red}theme not installed!${reset}"
    echo -e "Copy the contents of the theme to ${cyan}'${THEMES_DIR}/moos-nova/'${reset} and set the current theme to ${cyan}'moos-nova'${reset} in ${cyan}'/etc/sddm.conf.d/moos.conf'${reset}:\n"
    echo -e "    ${grey}# /etc/sddm.conf.d/moos.conf${reset}"
    echo -e "    [Theme]"
    echo -e "    Current=moos-nova"
fi
