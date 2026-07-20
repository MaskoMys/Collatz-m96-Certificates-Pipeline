#!/usr/bin/env bash
set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-navoy}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_AZ="${AWS_AZ:-}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c8a.8xlarge}"
VOLUME_SIZE_GIB="${VOLUME_SIZE_GIB:-200}"
JOBS="${JOBS:-30}"
KEY_NAME="${KEY_NAME:-sinruda}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
SSH_CIDR="${SSH_CIDR:-}"
PROJECT_TAG="${PROJECT_TAG:-collatz-v2}"
REPO_DIR="${REPO_DIR:-/work/Collatz-m96-Certificates-Pipeline}"
UBUNTU_AMI_PARAMETER="${UBUNTU_AMI_PARAMETER:-/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id}"

INSTANCE_NAME="${PROJECT_TAG}-compute"
VOLUME_NAME="${PROJECT_TAG}-data"
SECURITY_GROUP_NAME="${PROJECT_TAG}-ssh"
DEVICE_NAME="/dev/sdf"

usage() {
  cat <<'EOF'
Usage: scripts/aws_compute.sh COMMAND

Commands:
  create       Create the persistent disk if needed and launch/start the VM.
  status       Show the VM, persistent disk, and SSH command.
  sync         Transfer the exact local Git commit to a fresh data disk.
  ssh          Refresh the SSH rule and connect to the VM.
  stop         Stop the VM, preserving both its disks.
  destroy      Cleanly stop and terminate the VM; preserve the data disk.
  snapshot     Snapshot the persistent data disk.
  delete-data  Permanently delete the persistent data disk.

Defaults:
  AWS_PROFILE=navoy
  AWS_REGION=us-east-1
  INSTANCE_TYPE=c8a.8xlarge
  VOLUME_SIZE_GIB=200
  JOBS=30
  KEY_NAME=sinruda
  SSH_KEY_PATH=~/.ssh/id_ed25519

Every default can be overridden as an environment variable. Examples:
  AWS_AZ=us-east-1c scripts/aws_compute.sh create
  SSH_CIDR=203.0.113.7/32 scripts/aws_compute.sh ssh
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

note() {
  printf '%s\n' "$*" >&2
}

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

require_commands() {
  local command
  for command in aws curl ssh ssh-keygen git; do
    command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
  done
}

normalize_text() {
  local value="$1"
  if [[ "$value" == "None" ]]; then
    value=""
  fi
  printf '%s' "$value"
}

instance_id() {
  local value
  value="$(aws_cli ec2 describe-instances \
    --filters \
      "Name=tag:Project,Values=$PROJECT_TAG" \
      "Name=tag:Role,Values=compute" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text)"
  value="$(normalize_text "$value")"
  [[ "$value" != *$'\t'* && "$value" != *' '* ]] || \
    die "multiple managed instances found: $value"
  printf '%s' "$value"
}

instance_state() {
  local id="$1"
  aws_cli ec2 describe-instances \
    --instance-ids "$id" \
    --query 'Reservations[0].Instances[0].State.Name' \
    --output text
}

volume_id() {
  local value
  value="$(aws_cli ec2 describe-volumes \
    --filters \
      "Name=tag:Project,Values=$PROJECT_TAG" \
      "Name=tag:Role,Values=data" \
    --query 'Volumes[].VolumeId' \
    --output text)"
  value="$(normalize_text "$value")"
  [[ "$value" != *$'\t'* && "$value" != *' '* ]] || \
    die "multiple managed data volumes found: $value"
  printf '%s' "$value"
}

volume_az() {
  aws_cli ec2 describe-volumes \
    --volume-ids "$1" \
    --query 'Volumes[0].AvailabilityZone' \
    --output text
}

current_public_ip() {
  local ip
  ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || \
    die "could not determine a valid public IPv4 address"
  printf '%s/32' "$ip"
}

default_vpc_id() {
  local value
  value="$(aws_cli ec2 describe-vpcs \
    --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' \
    --output text)"
  value="$(normalize_text "$value")"
  [[ -n "$value" ]] || die "no default VPC found in $AWS_REGION"
  printf '%s' "$value"
}

subnet_for_az() {
  local az="$1"
  local value
  value="$(aws_cli ec2 describe-subnets \
    --filters \
      "Name=availability-zone,Values=$az" \
      Name=default-for-az,Values=true \
    --query 'Subnets[0].SubnetId' \
    --output text)"
  value="$(normalize_text "$value")"
  [[ -n "$value" ]] || die "no default subnet found in $az"
  printf '%s' "$value"
}

select_az() {
  local existing_volume="$1"
  local candidate

  if [[ -n "$existing_volume" ]]; then
    volume_az "$existing_volume"
    return
  fi

  if [[ -n "$AWS_AZ" ]]; then
    candidate="$AWS_AZ"
  else
    candidate="$(aws_cli ec2 describe-instance-type-offerings \
      --location-type availability-zone \
      --filters "Name=instance-type,Values=$INSTANCE_TYPE" \
      --query 'sort_by(InstanceTypeOfferings,&Location)[0].Location' \
      --output text)"
    candidate="$(normalize_text "$candidate")"
  fi
  [[ -n "$candidate" ]] || die "$INSTANCE_TYPE is not offered in $AWS_REGION"

  aws_cli ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters \
      "Name=instance-type,Values=$INSTANCE_TYPE" \
      "Name=location,Values=$candidate" \
    --query 'InstanceTypeOfferings[0].InstanceType' \
    --output text | grep -qx "$INSTANCE_TYPE" || \
      die "$INSTANCE_TYPE is not offered in $candidate"
  subnet_for_az "$candidate" >/dev/null
  printf '%s' "$candidate"
}

verify_key_pair() {
  [[ -f "$SSH_KEY_PATH" ]] || die "SSH private key not found: $SSH_KEY_PATH"

  local aws_public local_public
  aws_public="$(aws_cli ec2 describe-key-pairs \
    --key-names "$KEY_NAME" \
    --include-public-key \
    --query 'KeyPairs[0].PublicKey' \
    --output text 2>/dev/null)" || \
    die "EC2 key pair not found: $KEY_NAME"
  local_public="$(ssh-keygen -y -f "$SSH_KEY_PATH")"
  aws_public="$(awk '{print $1 " " $2}' <<<"$aws_public")"
  local_public="$(awk '{print $1 " " $2}' <<<"$local_public")"
  [[ "$aws_public" == "$local_public" ]] || \
    die "$SSH_KEY_PATH does not match EC2 key pair $KEY_NAME"
}

security_group_id() {
  local vpc_id="$1"
  local value
  value="$(aws_cli ec2 describe-security-groups \
    --filters \
      "Name=vpc-id,Values=$vpc_id" \
      "Name=group-name,Values=$SECURITY_GROUP_NAME" \
    --query 'SecurityGroups[0].GroupId' \
    --output text)"
  value="$(normalize_text "$value")"

  if [[ -z "$value" ]]; then
    value="$(aws_cli ec2 create-security-group \
      --group-name "$SECURITY_GROUP_NAME" \
      --description "SSH access for $PROJECT_TAG compute" \
      --vpc-id "$vpc_id" \
      --query GroupId \
      --output text)"
    aws_cli ec2 create-tags \
      --resources "$value" \
      --tags \
        "Key=Name,Value=$SECURITY_GROUP_NAME" \
        "Key=Project,Value=$PROJECT_TAG" \
        Key=ManagedBy,Value=aws_compute.sh
    note "Created security group $value."
  fi
  printf '%s' "$value"
}

refresh_ssh_rule() {
  local group_id="$1"
  local desired_cidr="${SSH_CIDR:-$(current_public_ip)}"
  local cidr

  [[ "$desired_cidr" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]] || \
    die "SSH_CIDR must be an IPv4 CIDR"

  while IFS= read -r cidr; do
    [[ -z "$cidr" || "$cidr" == "None" || "$cidr" == "$desired_cidr" ]] && continue
    aws_cli ec2 revoke-security-group-ingress \
      --group-id "$group_id" \
      --protocol tcp \
      --port 22 \
      --cidr "$cidr" >/dev/null
  done < <(aws_cli ec2 describe-security-groups \
    --group-ids "$group_id" \
    --query 'SecurityGroups[0].IpPermissions[?IpProtocol==`tcp` && FromPort==`22` && ToPort==`22`].IpRanges[].CidrIp' \
    --output text | tr '\t' '\n')

  if ! aws_cli ec2 describe-security-groups \
    --group-ids "$group_id" \
    --query 'SecurityGroups[0].IpPermissions[?IpProtocol==`tcp` && FromPort==`22` && ToPort==`22`].IpRanges[].CidrIp' \
    --output text | tr '\t' '\n' | grep -Fxq "$desired_cidr"; then
    aws_cli ec2 authorize-security-group-ingress \
      --group-id "$group_id" \
      --protocol tcp \
      --port 22 \
      --cidr "$desired_cidr" >/dev/null
  fi
  note "SSH is restricted to $desired_cidr."
}

ensure_volume() {
  local az="$1"
  local id="$2"
  if [[ -n "$id" ]]; then
    local existing_az
    existing_az="$(volume_az "$id")"
    [[ "$existing_az" == "$az" ]] || \
      die "data volume $id is in $existing_az, not $az"
    printf '%s' "$id"
    return
  fi

  id="$(aws_cli ec2 create-volume \
    --availability-zone "$az" \
    --size "$VOLUME_SIZE_GIB" \
    --volume-type gp3 \
    --encrypted \
    --tag-specifications \
      "ResourceType=volume,Tags=[{Key=Name,Value=$VOLUME_NAME},{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=data},{Key=ManagedBy,Value=aws_compute.sh}]" \
    --query VolumeId \
    --output text)"
  note "Created persistent data volume $id; waiting for it to become available."
  aws_cli ec2 wait volume-available --volume-ids "$id"
  printf '%s' "$id"
}

write_user_data() {
  local path="$1"
  local data_volume_id="$2"
  local commit="$3"

  {
    cat <<EOF
#!/usr/bin/env bash
set -euo pipefail
DATA_VOLUME_ID='$data_volume_id'
REPO_DIR='$REPO_DIR'
REPO_COMMIT='$commit'
JOBS='$JOBS'
EOF
    cat <<'EOF'

export DEBIAN_FRONTEND=noninteractive
apt-get update -o Acquire::Retries=5
apt-get install -y ca-certificates docker.io e2fsprogs git
systemctl enable --now docker
usermod -aG docker ubuntu

volume_token="${DATA_VOLUME_ID//-/}"
device_link="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volume_token}"
for _ in $(seq 1 120); do
  [[ -e "$device_link" ]] && break
  sleep 2
done
[[ -e "$device_link" ]] || {
  echo "Persistent EBS device did not appear: $device_link" >&2
  exit 1
}
device="$(readlink -f "$device_link")"

if ! blkid -s TYPE -o value "$device" | grep -q .; then
  mkfs.ext4 -L collatz-data "$device"
fi
uuid="$(blkid -s UUID -o value "$device")"
mkdir -p /work
if ! grep -q "UUID=$uuid" /etc/fstab; then
  printf 'UUID=%s /work ext4 defaults,nofail 0 2\n' "$uuid" >>/etc/fstab
fi
mountpoint -q /work || mount /work
chown ubuntu:ubuntu /work

cat >/etc/profile.d/collatz-v2.sh <<PROFILE
export JOBS=$JOBS
export COLLATZ_REPO=$REPO_DIR
PROFILE

cat >/work/START_HERE.txt <<INSTRUCTIONS
Persistent workspace: /work
Repository: $REPO_DIR
Authenticated source commit requested by the launcher: $REPO_COMMIT
Recommended concurrency: JOBS=$JOBS

The launcher transfers the private Git repository after this bootstrap finishes.
INSTRUCTIONS
chown ubuntu:ubuntu /work/START_HERE.txt
touch /work/.collatz-bootstrap-ready
chown ubuntu:ubuntu /work/.collatz-bootstrap-ready
EOF
  } >"$path"
}

public_ip() {
  aws_cli ec2 describe-instances \
    --instance-ids "$1" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
}

wait_for_bootstrap() {
  local id="$1"
  local ip attempt
  aws_cli ec2 wait instance-status-ok --instance-ids "$id"
  ip="$(normalize_text "$(public_ip "$id")")"
  [[ -n "$ip" ]] || die "instance has no public IP"
  for attempt in $(seq 1 120); do
    if ssh -i "$SSH_KEY_PATH" \
      -o BatchMode=yes \
      -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=5 \
      "ubuntu@$ip" \
      'test -f /work/.collatz-bootstrap-ready' >/dev/null 2>&1; then
      printf '%s' "$ip"
      return
    fi
    sleep 5
  done
  die "instance is reachable but bootstrap did not finish within 10 minutes"
}

sync_repository() {
  require_commands
  verify_key_pair
  local id state vpc_id group_id ip commit remote_head bundle remote_bundle
  id="$(instance_id)"
  [[ -n "$id" ]] || die "no managed instance; run create first"
  state="$(instance_state "$id")"
  [[ "$state" == "running" ]] || die "instance $id is $state, not running"
  vpc_id="$(default_vpc_id)"
  group_id="$(security_group_id "$vpc_id")"
  refresh_ssh_rule "$group_id"
  note "Waiting for instance health checks and /work bootstrap."
  ip="$(wait_for_bootstrap "$id")"
  commit="$(git rev-parse HEAD 2>/dev/null || true)"
  [[ -n "$commit" ]] || die "run this helper from a Git checkout"

  remote_head="$(ssh -i "$SSH_KEY_PATH" \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    "ubuntu@$ip" \
    "git -C '$REPO_DIR' rev-parse HEAD 2>/dev/null || true")"
  if [[ "$remote_head" == "$commit" ]]; then
    note "Remote repository already matches $commit."
    return
  fi
  if [[ -n "$remote_head" ]]; then
    note "Remote repository is at $remote_head; it may be replaced only if clean and no production run exists."
  fi

  bundle="$(mktemp --suffix=.bundle)"
  remote_bundle="/tmp/${PROJECT_TAG}-${commit}.bundle"
  trap 'rm -f "${bundle:-}"' RETURN
  git bundle create "$bundle" --all
  note "Transferring the private repository bundle."
  scp -q \
    -i "$SSH_KEY_PATH" \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    "$bundle" "ubuntu@$ip:$remote_bundle"
  ssh -i "$SSH_KEY_PATH" \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    "ubuntu@$ip" \
    bash -s -- "$REPO_DIR" "$commit" "$JOBS" "$remote_bundle" <<'REMOTE'
set -euo pipefail
repo_dir="$1"
commit="$2"
jobs="$3"
bundle="$4"
if [[ -d "$repo_dir/.git" ]]; then
  if [[ -e "$repo_dir/dist/search-v2" ]]; then
    echo "Refusing to change commits after dist/search-v2 exists." >&2
    exit 1
  fi
  if [[ -n "$(git -C "$repo_dir" status --porcelain --untracked-files=all)" ]]; then
    echo "Refusing to replace a modified remote checkout." >&2
    exit 1
  fi
  rm -rf "$repo_dir"
elif [[ -e "$repo_dir" ]]; then
  echo "Refusing to replace existing non-Git path: $repo_dir" >&2
  exit 1
fi
git clone "$bundle" "$repo_dir"
git -C "$repo_dir" checkout --detach "$commit"
rm -f "$bundle"
cat <<PROFILE | sudo tee /etc/profile.d/collatz-v2.sh >/dev/null
export JOBS=$jobs
export COLLATZ_REPO=$repo_dir
PROFILE
cat > /work/START_HERE.txt <<INSTRUCTIONS
Persistent workspace: /work
Repository: $repo_dir
Authenticated source commit: $commit
Recommended concurrency: JOBS=$jobs

Run:
  cd $repo_dir
  less README.md
INSTRUCTIONS
REMOTE
  rm -f "$bundle"
  trap - RETURN
  note "Remote repository is ready at $REPO_DIR ($commit)."
}

show_connection() {
  local id="$1"
  local ip
  ip="$(normalize_text "$(public_ip "$id")")"
  if [[ -n "$ip" ]]; then
    printf 'SSH: ssh -i %q ubuntu@%s\n' "$SSH_KEY_PATH" "$ip"
  else
    printf 'SSH: public IP not assigned yet\n'
  fi
}

create_instance() {
  require_commands
  verify_key_pair

  local id state existing_volume az subnet_id vpc_id group_id data_volume ami commit user_data
  id="$(instance_id)"
  if [[ -n "$id" ]]; then
    state="$(instance_state "$id")"
    case "$state" in
      running)
        note "Instance $id is already running."
        ;;
      pending)
        note "Instance $id is already starting."
        ;;
      stopping)
        note "Waiting for instance $id to stop before restarting it."
        aws_cli ec2 wait instance-stopped --instance-ids "$id"
        aws_cli ec2 start-instances --instance-ids "$id" >/dev/null
        ;;
      stopped)
        note "Starting existing instance $id."
        aws_cli ec2 start-instances --instance-ids "$id" >/dev/null
        ;;
      *) die "unexpected instance state: $state" ;;
    esac
    aws_cli ec2 wait instance-running --instance-ids "$id"
    vpc_id="$(default_vpc_id)"
    group_id="$(security_group_id "$vpc_id")"
    refresh_ssh_rule "$group_id"
    show_connection "$id"
    sync_repository
    return
  fi

  existing_volume="$(volume_id)"
  az="$(select_az "$existing_volume")"
  subnet_id="$(subnet_for_az "$az")"
  vpc_id="$(default_vpc_id)"
  group_id="$(security_group_id "$vpc_id")"
  refresh_ssh_rule "$group_id"
  data_volume="$(ensure_volume "$az" "$existing_volume")"
  ami="$(aws_cli ssm get-parameter \
    --name "$UBUNTU_AMI_PARAMETER" \
    --query 'Parameter.Value' \
    --output text)"
  commit="$(git rev-parse HEAD 2>/dev/null || true)"
  [[ -n "$commit" ]] || die "run this helper from a Git checkout"
  user_data="$(mktemp)"
  trap 'rm -f "${user_data:-}"' EXIT
  write_user_data "$user_data" "$data_volume" "$commit"

  note "Launching $INSTANCE_TYPE in $az from $ami."
  id="$(aws_cli ec2 run-instances \
    --image-id "$ami" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --subnet-id "$subnet_id" \
    --security-group-ids "$group_id" \
    --associate-public-ip-address \
    --instance-initiated-shutdown-behavior stop \
    --metadata-options HttpTokens=required,HttpEndpoint=enabled \
    --block-device-mappings \
      'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}' \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=compute},{Key=ManagedBy,Value=aws_compute.sh}]" \
      "ResourceType=volume,Tags=[{Key=Name,Value=${PROJECT_TAG}-root},{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=root},{Key=ManagedBy,Value=aws_compute.sh}]" \
    --user-data "file://$user_data" \
    --query 'Instances[0].InstanceId' \
    --output text)"

  note "Created instance $id; waiting for it to run."
  aws_cli ec2 wait instance-running --instance-ids "$id"
  aws_cli ec2 attach-volume \
    --volume-id "$data_volume" \
    --instance-id "$id" \
    --device "$DEVICE_NAME" >/dev/null
  note "Attached persistent data volume $data_volume."
  note "Cloud-init will need a few minutes to install Docker and prepare /work."
  show_connection "$id"
  sync_repository
}

show_status() {
  require_commands
  local id data_volume
  id="$(instance_id)"
  data_volume="$(volume_id)"

  if [[ -n "$id" ]]; then
    aws_cli ec2 describe-instances \
      --instance-ids "$id" \
      --query 'Reservations[0].Instances[0].{Id:InstanceId,Name:Tags[?Key==`Name`]|[0].Value,State:State.Name,Type:InstanceType,AZ:Placement.AvailabilityZone,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress,LaunchTime:LaunchTime}' \
      --output table
    show_connection "$id"
  else
    echo "No managed instance."
  fi

  if [[ -n "$data_volume" ]]; then
    aws_cli ec2 describe-volumes \
      --volume-ids "$data_volume" \
      --query 'Volumes[0].{Id:VolumeId,Name:Tags[?Key==`Name`]|[0].Value,State:State,AZ:AvailabilityZone,SizeGiB:Size,Type:VolumeType,Encrypted:Encrypted,AttachedTo:Attachments[0].InstanceId}' \
      --output table
  else
    echo "No persistent data volume."
  fi
}

ssh_instance() {
  require_commands
  verify_key_pair
  local id state vpc_id group_id ip
  id="$(instance_id)"
  [[ -n "$id" ]] || die "no managed instance; run create first"
  state="$(instance_state "$id")"
  [[ "$state" == "running" ]] || die "instance $id is $state, not running"
  vpc_id="$(default_vpc_id)"
  group_id="$(security_group_id "$vpc_id")"
  refresh_ssh_rule "$group_id"
  ip="$(normalize_text "$(public_ip "$id")")"
  [[ -n "$ip" ]] || die "instance has no public IP"
  exec ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=accept-new "ubuntu@$ip"
}

stop_instance() {
  require_commands
  local id state
  id="$(instance_id)"
  [[ -n "$id" ]] || die "no managed instance"
  state="$(instance_state "$id")"
  case "$state" in
    pending)
      aws_cli ec2 wait instance-running --instance-ids "$id"
      aws_cli ec2 stop-instances --instance-ids "$id" >/dev/null
      ;;
    running)
      aws_cli ec2 stop-instances --instance-ids "$id" >/dev/null
      ;;
    stopping) ;;
    stopped)
      note "Instance $id is already stopped."
      return
      ;;
    *) die "unexpected instance state: $state" ;;
  esac
  note "Waiting for instance $id to stop cleanly."
  aws_cli ec2 wait instance-stopped --instance-ids "$id"
  note "Instance stopped; EBS storage continues to persist."
}

confirm() {
  local prompt="$1"
  if [[ "${COLLATZ_ASSUME_YES:-0}" == "1" ]]; then
    return
  fi
  [[ -t 0 ]] || die "confirmation required; rerun interactively or set COLLATZ_ASSUME_YES=1"
  local answer
  read -r -p "$prompt [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || die "cancelled"
}

destroy_instance() {
  require_commands
  local id state data_volume
  id="$(instance_id)"
  [[ -n "$id" ]] || die "no managed instance"
  confirm "Terminate instance $id while preserving the data volume?"
  state="$(instance_state "$id")"
  if [[ "$state" != "stopped" ]]; then
    stop_instance
  fi
  aws_cli ec2 terminate-instances --instance-ids "$id" >/dev/null
  note "Waiting for instance $id to terminate."
  aws_cli ec2 wait instance-terminated --instance-ids "$id"
  data_volume="$(volume_id)"
  if [[ -n "$data_volume" ]]; then
    aws_cli ec2 wait volume-available --volume-ids "$data_volume"
    note "Instance terminated. Persistent data remains on $data_volume."
  fi
}

snapshot_volume() {
  require_commands
  local data_volume snapshot_id
  data_volume="$(volume_id)"
  [[ -n "$data_volume" ]] || die "no persistent data volume"
  snapshot_id="$(aws_cli ec2 create-snapshot \
    --volume-id "$data_volume" \
    --description "$PROJECT_TAG data snapshot" \
    --tag-specifications \
      "ResourceType=snapshot,Tags=[{Key=Name,Value=${PROJECT_TAG}-data-snapshot},{Key=Project,Value=$PROJECT_TAG},{Key=ManagedBy,Value=aws_compute.sh}]" \
    --query SnapshotId \
    --output text)"
  note "Started snapshot $snapshot_id from $data_volume."
}

delete_data_volume() {
  require_commands
  local id data_volume state
  id="$(instance_id)"
  [[ -z "$id" ]] || die "destroy the managed instance before deleting its data volume"
  data_volume="$(volume_id)"
  [[ -n "$data_volume" ]] || die "no persistent data volume"
  state="$(aws_cli ec2 describe-volumes \
    --volume-ids "$data_volume" \
    --query 'Volumes[0].State' \
    --output text)"
  [[ "$state" == "available" ]] || die "volume $data_volume is $state, not available"
  [[ "${COLLATZ_CONFIRM_DELETE_VOLUME:-}" == "$data_volume" ]] || \
    die "permanent deletion requires COLLATZ_CONFIRM_DELETE_VOLUME=$data_volume"
  confirm "Permanently delete data volume $data_volume and all computation on it?"
  aws_cli ec2 delete-volume --volume-id "$data_volume"
  note "Deleted persistent data volume $data_volume."
}

main() {
  case "${1:-}" in
    create|start) create_instance ;;
    status) show_status ;;
    sync) sync_repository ;;
    ssh) ssh_instance ;;
    stop) stop_instance ;;
    destroy) destroy_instance ;;
    snapshot) snapshot_volume ;;
    delete-data) delete_data_volume ;;
    -h|--help|help|'') usage ;;
    *) usage >&2; die "unknown command: $1" ;;
  esac
}

main "$@"
